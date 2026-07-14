from __future__ import annotations
import re
from cognigy_mcp.tools.flow_ops import _RESOURCE_TYPE_ALIASES

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
