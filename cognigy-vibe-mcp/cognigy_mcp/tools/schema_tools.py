from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.tools.flow_ops import _RESOURCE_TYPE_ALIASES
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema

_OPERATION_METHOD: dict[str, str] = {
    "create": "post",
    "update": "patch",
    "get": "get",
    "list": "get",
    "delete": "delete",
}

_TOP_LEVEL_PATH_RE = re.compile(r"^/v2\.0/[a-zA-Z]+$")


def _normalise_rtype(rtype: str) -> str:
    return _RESOURCE_TYPE_ALIASES.get(rtype.lower(), rtype.lower())


def _find_candidate_path(paths: dict, rtype: str, operation: str) -> tuple[str | None, bool]:
    if operation in ("create", "list"):
        candidate = f"/v2.0/{rtype}"
        if candidate in paths:
            return candidate, True
    else:
        prefix = f"/v2.0/{rtype}/"
        for p in paths:
            if p.startswith(prefix):
                remainder = p[len(prefix) :]
                if remainder.startswith("{") and remainder.endswith("}") and "/" not in remainder:
                    return p, True
    for p in sorted(paths):
        if rtype in p:
            return p, False
    return None, False


def _known_resource_types(paths: dict) -> list[str]:
    return sorted(p.split("/")[2] for p in paths if _TOP_LEVEL_PATH_RE.match(p))


def _properties_from_schema(schema: dict) -> tuple[dict, set[str]]:
    return schema.get("properties", {}), set(schema.get("required", []))


def _extract_fields(op: dict, operation: str) -> list[dict]:
    if operation in ("create", "update"):
        schema = (
            op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
        )
        props, required = _properties_from_schema(schema)
        fields = []
        for name, prop in props.items():
            entry = {"field": name, "type": prop.get("type", "object"), "required": name in required}
            for key in ("enum", "example", "description"):
                if key in prop:
                    entry[key] = prop[key]
            fields.append(entry)
        return fields
    if operation == "get":
        schema = (
            op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
        )
        props, _ = _properties_from_schema(schema)
        fields = []
        for name, prop in props.items():
            entry = {"field": name, "type": prop.get("type", "object")}
            for key in ("enum", "example", "description"):
                if key in prop:
                    entry[key] = prop[key]
            fields.append(entry)
        return fields
    if operation == "list":
        fields = []
        for param in op.get("parameters", []):
            if param.get("in") != "query":
                continue
            entry = {
                "field": param["name"],
                "type": param.get("schema", {}).get("type", "string"),
                "required": param.get("required", False),
            }
            for key in ("description", "example"):
                if key in param:
                    entry[key] = param[key]
            fields.append(entry)
        return fields
    return []  # delete takes no body


def _raw_schema_fragment(op: dict, operation: str) -> dict:
    if operation in ("create", "update"):
        return op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if operation == "get":
        return op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if operation == "list":
        return {"parameters": [p for p in op.get("parameters", []) if p.get("in") == "query"]}
    return {}


class DescribeResourceSchemaArgs(BaseModel):
    resource_type: str = Field(description="e.g. flows, lexicons, endpoints, connections")
    operation: Literal["create", "update", "get", "list", "delete"]
    verbose: bool = Field(
        False,
        description="When true, return the raw OpenAPI schema fragment instead of a simplified field list.",
    )


TOOLS: list[Tool] = [
    Tool(
        name="describe_resource_schema",
        description=(
            "Look up the field-level shape for a Cognigy resource_type + operation "
            "(create/update/get/list/delete), derived from the live OpenAPI spec (cached ~24h). "
            "Use this before guessing a body for cognigy_create/cognigy_update against an "
            "unfamiliar resource_type — cheaper than trial-and-error against live API 400s. "
            "NOTE: for resource_type='node', only the generic envelope (type/mode/target/label/etc.) "
            "is covered here — a node's 'config' shape is node-type-specific and NOT in the OpenAPI "
            "spec; use explain() for per-node-type config topics (e.g. say-node) instead."
        ),
        inputSchema=make_schema(DescribeResourceSchemaArgs),
    ),
]


def _api_error_response(exc: ApiError) -> list[TextContent]:
    return _ok({"error": "api_error", "status": exc.status_code, "detail": str(exc)})


def _unexpected_error_response(exc: Exception) -> list[TextContent]:
    return _ok({"error": "unexpected_error", "detail": str(exc)})


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:
    spec_cache = Cache(cache_dir=cache.cache_dir, ttl=86400)

    def _describe_resource_schema(args: dict) -> list[TextContent]:
        m, err = validate(DescribeResourceSchemaArgs, args)
        if err:
            return err

        cached_spec, fresh = spec_cache.get("openapi", "spec")
        if fresh and cached_spec:
            spec = cached_spec
        else:
            try:
                spec = client.get_openapi_spec()
            except ApiError as exc:
                return _api_error_response(exc)
            except Exception as exc:
                return _unexpected_error_response(exc)
            spec_cache.set("openapi", "spec", spec)

        paths = spec.get("paths", {})
        rtype = _normalise_rtype(m.resource_type)
        path, exact = _find_candidate_path(paths, rtype, m.operation)
        if path is None:
            return _ok({
                "error": f"No OpenAPI path found for resource_type={m.resource_type!r}",
                "known_resource_types": _known_resource_types(paths),
            })

        method = _OPERATION_METHOD[m.operation]
        available_methods = sorted(paths[path].keys())
        if method not in available_methods:
            return _ok({
                "error": (
                    f"operation={m.operation!r} (HTTP {method.upper()}) not available at {path}"
                ),
                "available_methods": available_methods,
            })

        op = paths[path][method]
        result = {
            "resource_type": rtype,
            "operation": m.operation,
            "path": path,
            "method": method,
        }
        if not exact:
            result["warning"] = (
                f"No exact match for resource_type={m.resource_type!r}; "
                f"best guess via substring search: {path}"
            )
        if m.verbose:
            result["raw_schema"] = _raw_schema_fragment(op, m.operation)
        else:
            result["fields"] = _extract_fields(op, m.operation)
        return _ok(result)

    return {"describe_resource_schema": _describe_resource_schema}
