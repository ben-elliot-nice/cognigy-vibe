from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.tools.flow_ops import (
    _RESOURCE_TYPE_ALIASES,
    _api_error_response,
    _unexpected_error_response,
)
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


# Intentionally lowercases on an alias-miss (unlike flow_ops._normalise_rtype, which
# preserves original case on a miss) because OpenAPI path segments are always lowercase
# — the fallback here feeds directly into path lookups such as f"/v2.0/{rtype}".
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


_COMPOSITION_KEYS = ("$ref", "oneOf", "allOf", "anyOf")


def _is_composed_schema(schema: dict) -> bool:
    """True when a schema has no flat 'properties' but uses $ref/oneOf/allOf/anyOf
    composition instead — extracting fields from these would silently yield []."""
    return "properties" not in schema and any(key in schema for key in _COMPOSITION_KEYS)


_COMPONENTS_SCHEMA_REF_RE = re.compile(r"^#/components/schemas/([^/]+)$")


def _resolve_component_ref(ref: str, spec: dict) -> dict | None:
    """Resolve a '#/components/schemas/X' JSON Pointer against spec['components']['schemas'].
    Returns None if the ref isn't of that shape or doesn't resolve to anything — this is
    intentionally NOT a general recursive JSON-Pointer resolver, just the one shape OpenAPI
    specs actually use for named schema components."""
    match = _COMPONENTS_SCHEMA_REF_RE.match(ref)
    if not match:
        return None
    name = match.group(1)
    return spec.get("components", {}).get("schemas", {}).get(name)


def _resolve_schema_ref(schema: dict, spec: dict) -> dict:
    """Resolve a bare {"$ref": "#/components/schemas/X"} schema fragment (or a
    single-level allOf wrapping one) against the full spec's components.schemas.
    Falls back to returning the schema unchanged if it isn't a $ref/allOf-$ref shape,
    or if the ref doesn't resolve to anything in components.schemas."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        resolved = _resolve_component_ref(ref, spec)
        return resolved if resolved is not None else schema

    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        merged_properties: dict = {}
        merged_required: set[str] = set()
        resolved_any = False
        for entry in all_of:
            if not isinstance(entry, dict):
                continue
            entry_ref = entry.get("$ref")
            if isinstance(entry_ref, str):
                resolved = _resolve_component_ref(entry_ref, spec)
                if resolved is None:
                    continue
                resolved_any = True
                merged_properties.update(resolved.get("properties", {}))
                merged_required.update(resolved.get("required", []))
            else:
                merged_properties.update(entry.get("properties", {}))
                merged_required.update(entry.get("required", []))
        if resolved_any:
            return {"type": "object", "properties": merged_properties, "required": sorted(merged_required)}
        return schema

    return schema


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


def _with_resolved_schema(op: dict, operation: str, spec: dict) -> dict:
    """Return a copy of `op` with its request-body ('create'/'update') or 200-response
    ('get') schema replaced by its $ref/allOf-$ref resolved form (see _resolve_schema_ref),
    so downstream _extract_fields/_is_composed_schema/_raw_schema_fragment all see the
    resolved schema uniformly, whether verbose or simplified mode is requested."""
    raw = _raw_schema_fragment(op, operation)
    if not isinstance(raw, dict):
        return op
    resolved = _resolve_schema_ref(raw, spec)
    if resolved is raw:
        return op
    if operation in ("create", "update"):
        return {
            **op,
            "requestBody": {
                **op.get("requestBody", {}),
                "content": {
                    **op.get("requestBody", {}).get("content", {}),
                    "application/json": {
                        **op.get("requestBody", {}).get("content", {}).get("application/json", {}),
                        "schema": resolved,
                    },
                },
            },
        }
    # operation == "get"
    return {
        **op,
        "responses": {
            **op.get("responses", {}),
            "200": {
                **op.get("responses", {}).get("200", {}),
                "content": {
                    **op.get("responses", {}).get("200", {}).get("content", {}),
                    "application/json": {
                        **op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}),
                        "schema": resolved,
                    },
                },
            },
        },
    }


def _merge_path_item_parameters(path_item: dict, op: dict) -> list[dict]:
    """Merge path-item-level 'parameters' (a sibling of get/post/etc, applying to all
    methods on that path) with operation-level 'parameters'. Operation-level wins on
    a name+location collision, per the OpenAPI spec (more specific overrides shared)."""
    merged: dict[tuple[str, str], dict] = {}
    for param in path_item.get("parameters", []):
        merged[(param.get("name"), param.get("in"))] = param
    for param in op.get("parameters", []):
        merged[(param.get("name"), param.get("in"))] = param
    return list(merged.values())


def _raw_schema_fragment(op: dict, operation: str) -> dict:
    if operation in ("create", "update"):
        return op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if operation == "get":
        return op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if operation == "list":
        return {"parameters": [p for p in op.get("parameters", []) if p.get("in") == "query"]}
    return {}


def _known_node_types(descriptors: list[dict]) -> list[str]:
    return sorted({d.get("type") for d in descriptors if d.get("type")})


def _find_node_descriptor(descriptors: list[dict], node_type: str) -> dict | None:
    for descriptor in descriptors:
        if descriptor.get("type") == node_type:
            return descriptor
    return None


def _simplify_descriptor_fields(fields: list[dict]) -> list[dict]:
    """Flatten a chart/descriptors node-type's raw fields[] (UI-editor field metadata:
    key/type/label/defaultValue/condition/params.options) into the same
    {field, type, ...} shape describe_resource_schema already returns for
    OpenAPI-derived fields, so callers don't need two different result shapes."""
    simplified = []
    for descriptor_field in fields:
        entry = {
            "field": descriptor_field.get("key"),
            "type": descriptor_field.get("type"),
        }
        for key in ("label", "description", "condition"):
            if key in descriptor_field:
                entry[key] = descriptor_field[key]
        if "defaultValue" in descriptor_field:
            entry["default"] = descriptor_field["defaultValue"]
        params = descriptor_field.get("params") or {}
        if "required" in params:
            entry["required"] = params["required"]
        if "options" in params:
            entry["enum"] = [
                option.get("value") for option in params["options"] if isinstance(option, dict)
            ]
        simplified.append(entry)
    return simplified


class DescribeResourceSchemaArgs(BaseModel):
    resource_type: str = Field(description="e.g. flows, lexicons, endpoints, connections")
    operation: Literal["create", "update", "get", "list", "delete"] | None = Field(
        None,
        description="Required unless node_type is set — a node_type lookup returns a "
        "config field schema directly, not a CRUD operation's schema.",
    )
    node_type: str | None = Field(
        None,
        description="When resource_type='node', pass the node's type (e.g. 'say', "
        "'aiAgentJob', or a 3rd-party extension node type) to fetch its live config "
        "field schema from GET /v2.0/flows/{flowId}/chart/descriptors. Requires flow_id.",
    )
    flow_id: str | None = Field(
        None,
        description="Required when node_type is set. Any flow _id in the project works — "
        "chart/descriptors returns the project-wide node-type catalog, not per-flow data.",
    )
    verbose: bool = Field(
        False,
        description="When true, return the raw OpenAPI schema fragment (or raw descriptor "
        "fields, for node_type lookups) instead of a simplified field list.",
    )


TOOLS: list[Tool] = [
    Tool(
        name="describe_resource_schema",
        description=(
            "Look up the field-level shape for a Cognigy resource_type + operation "
            "(create/update/get/list/delete), derived from the live OpenAPI spec (cached ~24h). "
            "Use this before guessing a body for cognigy_create/cognigy_update against an "
            "unfamiliar resource_type — cheaper than trial-and-error against live API 400s. "
            "For resource_type='node', the OpenAPI spec only covers the generic envelope "
            "(type/mode/target/label/etc.) — a node's 'config' shape is node-type-specific and "
            "lives in the live node-descriptor catalog instead. Pass node_type (e.g. 'say') plus "
            "flow_id to fetch that node type's live config field schema "
            "(GET /v2.0/flows/{flowId}/chart/descriptors, cached ~24h) instead of the generic envelope."
        ),
        inputSchema=make_schema(DescribeResourceSchemaArgs),
    ),
]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:
    spec_cache = Cache(cache_dir=cache.cache_dir, ttl=86400)

    def _describe_resource_schema(args: dict) -> list[TextContent]:
        m, err = validate(DescribeResourceSchemaArgs, args)
        if err:
            return err

        if m.node_type is not None:
            if _normalise_rtype(m.resource_type) != "node":
                return _ok({
                    "error": f"node_type is only valid with resource_type='node', got {m.resource_type!r}",
                })
            return _describe_node_type_schema(m)

        if m.operation is None:
            return _ok({"error": "operation is required unless node_type is set"})

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

        # Everything below reaches into the live, externally-controlled spec content
        # (paths, path-item keys, operation objects, request/response schema fragments) —
        # any structural surprise (unexpected types, missing keys) must come back as
        # a clean error envelope rather than an unhandled exception. This is why the
        # try block starts here, before paths/rtype/path are even derived, rather than
        # only around the later per-operation lookups.
        rtype = path = method = None
        try:
            paths = spec.get("paths", {})
            rtype = _normalise_rtype(m.resource_type)
            path, exact = _find_candidate_path(paths, rtype, m.operation)
            if path is None:
                return _ok({
                    "error": f"No OpenAPI path found for resource_type={m.resource_type!r}",
                    "known_resource_types": _known_resource_types(paths),
                })

            method = _OPERATION_METHOD[m.operation]

            available_methods = sorted(
                k for k in paths[path].keys() if k in _OPERATION_METHOD.values()
            )
            if method not in available_methods:
                error_response = {
                    "error": (
                        f"operation={m.operation!r} (HTTP {method.upper()}) not available at {path}"
                    ),
                    "available_methods": available_methods,
                }
                if not exact:
                    error_response["warning"] = (
                        f"No exact match for resource_type={m.resource_type!r}; "
                        f"best guess via substring search: {path}"
                    )
                return _ok(error_response)

            op = paths[path][method]
            if m.operation == "list":
                op = {**op, "parameters": _merge_path_item_parameters(paths[path], op)}
            elif m.operation in ("create", "update", "get"):
                op = _with_resolved_schema(op, m.operation, spec)
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
                if m.operation in ("create", "update", "get") and not result["fields"]:
                    schema_fragment = _raw_schema_fragment(op, m.operation)
                    if _is_composed_schema(schema_fragment):
                        schema_kind = "request body" if m.operation in ("create", "update") else "response"
                        result["note"] = (
                            f"This resource's {schema_kind} schema uses $ref/oneOf/allOf/anyOf "
                            "composition rather than a flat 'properties' object, so it "
                            "could not be flattened into a field list. Call again with "
                            "verbose=True to see the raw schema fragment."
                        )
        except (AttributeError, TypeError, KeyError, IndexError) as exc:
            # rtype/path/method are initialized to None before this try block, so they
            # are always defined here even if the exception was raised while deriving
            # them (e.g. a malformed spec['paths']).
            return _ok({
                "error": "schema_parse_error",
                "detail": str(exc),
                "resource_type": rtype,
                "operation": m.operation,
                "path": path,
                "method": method,
            })
        return _ok(result)

    def _describe_node_type_schema(m: DescribeResourceSchemaArgs) -> list[TextContent]:
        if not m.flow_id:
            return _ok({"error": "flow_id is required when node_type is set"})

        # chart/descriptors returns the project-wide node-type catalog (verified live:
        # identical content regardless of which flow_id in the project is queried), so
        # the cache is keyed by project_id, not flow_id — otherwise every distinct
        # flow_id a caller passes would be an avoidable cache miss for the same data.
        cache_key = state.project_id or "_unscoped"
        cached_descriptors, fresh = spec_cache.get("chart_descriptors", cache_key)
        next_cursor = None
        if fresh and cached_descriptors is not None:
            descriptors = cached_descriptors
        else:
            try:
                resp = client.get(f"/v2.0/flows/{m.flow_id}/chart/descriptors")
            except ApiError as exc:
                return _api_error_response(exc)
            except Exception as exc:
                return _unexpected_error_response(exc)
            descriptors = resp.get("items", []) if isinstance(resp, dict) else resp
            next_cursor = resp.get("nextCursor") if isinstance(resp, dict) else None
            spec_cache.set("chart_descriptors", cache_key, descriptors)

        descriptor = _find_node_descriptor(descriptors, m.node_type)
        if descriptor is None:
            return _ok({
                "error": f"No node descriptor found for node_type={m.node_type!r}",
                "known_node_types": _known_node_types(descriptors),
            })

        result = {"resource_type": "node", "node_type": m.node_type, "flow_id": m.flow_id}
        # This endpoint's OpenAPI operation (indexNodeDescriptors_2_0) takes no query
        # parameters and its documented response schema declares only 'items' — no
        # cursor/limit params exist to page through, so a non-null nextCursor here
        # would mean the live API added pagination this client doesn't yet support.
        # Surface that as a warning rather than silently returning a partial catalog.
        if next_cursor:
            result["warning"] = (
                "API response included a non-null nextCursor, which this tool does not "
                "yet follow — the node-type catalog below may be incomplete."
            )
        raw_fields = descriptor.get("fields", [])
        if m.verbose:
            result["raw_fields"] = raw_fields
        else:
            result["fields"] = _simplify_descriptor_fields(raw_fields)
        return _ok(result)

    return {"describe_resource_schema": _describe_resource_schema}
