from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState, _deep_merge
from cognigy_mcp.filters import strip_response, BLOCKED_IN_CONFIG
from cognigy_mcp.validation import _ok, validate, make_schema


class CognigyGetArgs(BaseModel):
    resource_type: str = Field(description="e.g. flows, aiagents, endpoints")
    resource_id: str
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")
    fields: list[str] | None = Field(
        None,
        description="Optional: return only these keys. Example: fields=['_id','name'] reduces size by ~80%.",
    )


class CognigyListArgs(BaseModel):
    resource_type: str
    project_id: str | None = None
    agent_id: str | None = None
    limit: int = 100
    full_objects: bool = Field(
        False,
        description="When true, returns complete objects. Default false returns simplified {id, name} pairs (~95% token savings).",
    )
    fields: list[str] | None = Field(
        None,
        description="Optional: return only these keys from each item. Applied after full_objects filter.",
    )


class CognigyCreateArgs(BaseModel):
    resource_type: str
    body: dict
    flow_id: str | None = Field(None, description="Required when creating nodes")
    return_full_object: bool = Field(
        False,
        description="When true, returns the complete created object. Default false returns minimal {_id, referenceId, type, label} (~90% token savings).",
    )


class CognigyUpdateArgs(BaseModel):
    resource_type: str
    resource_id: str
    body: dict
    merge_config: bool = Field(
        False,
        description="When true, deep-merges body.config with current config rather than replacing",
    )
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")
    return_full_object: bool = Field(
        False,
        description="When true, returns the complete updated object. Default false returns minimal {_id, type, label} (~90% token savings).",
    )


class CognigyDeleteArgs(BaseModel):
    resource_type: str
    resource_id: str
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")


class CognigyInvokeArgs(BaseModel):
    resource_type: str
    resource_id: str
    operation: str
    body: dict = Field(default_factory=dict)
    flow_id: str | None = Field(None, description="Required for node operations")


class GetFlowChartArgs(BaseModel):
    flow_id: str
    format: Literal["hierarchy", "raw", "both"] = Field(
        "hierarchy",
        description="'hierarchy': tree string only (~95% savings, default). 'raw': nodes + relations arrays. 'both': current behavior (explicit opt-in).",
    )


_DISCOVERY_POINTER = (
    " For resource_types without an obvious body shape, call explain() for the "
    "topic index before guessing — trial-and-error against live API errors is the "
    "fallback of last resort, not the first move."
)

TOOLS: list[Tool] = [
    Tool(
        name="cognigy_get",
        description="GET any Cognigy resource by ID. Cache-first (5-min TTL). "
                    "Response includes _source: 'cache' or 'api'." + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyGetArgs),
    ),
    Tool(
        name="cognigy_list",
        description="List Cognigy resources. Pass project_id for project-scoped resources, "
                    "agent_id for agent-scoped resources (e.g. listing jobs). "
                    "resource_type accepts both singular ('flow') and plural ('flows'), and also "
                    "supports nested sub-resource paths, e.g. resource_type=\"knowledgestores/{id}/connectors\" "
                    "lists a knowledge store's connectors. "
                    "Default: returns simplified {id, name} pairs. Use full_objects=true for complete objects."
                    + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyListArgs),
    ),
    Tool(
        name="cognigy_create",
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include: "
                    "type (e.g. 'say', 'code', 'once', 'httpRequest', 'aiAgentJob'), "
                    "mode — one of: 'appendChild' (add as child of container node — use push_agent_tool for aiAgentJobTool nodes), "
                    "'append' (add as sibling after target — also the correct mode for Once/IF branch insertion: "
                    "target the branch marker _id, not the parent Once/IF node), "
                    "'insertAfter' or 'insertBefore' (may return 500 on AU1 — use append instead), "
                    "target (the _id of the reference node), "
                    "and flowId (the flow _id)."
                    + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyCreateArgs),
    ),
    Tool(
        name="cognigy_update",
        description="PATCH a Cognigy resource. WARNING: Cognigy PATCH is full-replace on 'config' — "
                    "set merge_config=true to deep-merge instead of overwriting. Always use merge_config=true "
                    "for partial config updates. "
                    "NOTE: with return_full_object=false (default), the response reflects whatever the API "
                    "actually returns — on some resource_types this can be a bare {} even on a successful write, "
                    "not the documented minimal {_id, type, label}. If you need write confirmation, re-fetch via "
                    "cognigy_get rather than relying on this response."
                    + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyUpdateArgs),
    ),
    Tool(
        name="cognigy_delete",
        description="DELETE a Cognigy resource. For nodes, pass flow_id." + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyDeleteArgs),
    ),
    Tool(
        name="cognigy_invoke",
        description="Run a named operation on a Cognigy resource. "
                    "Operations: node/move, flow/clone, aiagent/train, "
                    "knowledgestore/run, sessions/inject-context, sessions/inject-state."
                    + _DISCOVERY_POINTER,
        inputSchema=make_schema(CognigyInvokeArgs),
    ),
    Tool(
        name="get_flow_chart",
        description="Fetch the full chart for a flow. Default: returns human-readable hierarchy string. "
                    "Use format='raw' for structured arrays or format='both' for the legacy combined response.",
        inputSchema=make_schema(GetFlowChartArgs),
    ),
]


# ---------------------------------------------------------------------------
# P1 — Node config normalisation
# ---------------------------------------------------------------------------

_ANSWER_CANONICAL = "{{JSON.stringify(context.toolResponse)}}"
_ANSWER_MAX_LOOPS_DEFAULT = 4


def _normalise_answer_config(config: dict) -> dict:
    """Inject the canonical answer field if absent on aiAgentToolAnswer nodes.
    A bare config:{} returns an empty tool result; the LLM sees nothing back."""
    if "answer" in config:
        return config
    return {"answer": _ANSWER_CANONICAL, "maxLoops": _ANSWER_MAX_LOOPS_DEFAULT, **config}


_SAY_CONFIG_DEFAULTS = {
    "handoverOutput": "userAndAgent",
    "preventTranscript": False,
    "generativeAI_rephraseOutputMode": "none",
    "generativeAI_amountOfLastUserInputs": 5,
    "generativeAI_customInputs": "",
}


def _normalise_say_config(config: dict) -> dict:
    """Lift config.text → config.say.text envelope for Say nodes.
    No-op if 'say' key already present or no 'text' key."""
    if "say" in config or "text" not in config:
        return config
    text = config["text"]
    if isinstance(text, str):
        text = [text]
    result = {k: v for k, v in config.items() if k != "text"}
    result = {**_SAY_CONFIG_DEFAULTS, **result, "say": {
        "type": "text", "text": text, "data": "", "linear": False, "loop": False
    }}
    return result


# ---------------------------------------------------------------------------
# P2 — Extension auto-injection
# ---------------------------------------------------------------------------

_NODE_EXTENSION_MAP: dict[str, str] = {
    # Voice gateway nodes
    "setSessionConfig": "@cognigy/voicegateway2",
    "hangup": "@cognigy/voicegateway2",
    "sendMetadata": "@cognigy/voicegateway2",
    # AI agent nodes — registered under @cognigy/basic-nodes (not the legacy cognigy-ai-agent extension)
    "aiAgentJob": "@cognigy/basic-nodes",
    "aiAgentJobTool": "@cognigy/basic-nodes",
    "aiAgentToolAnswer": "@cognigy/basic-nodes",
    # xApp nodes
    "initAppSession": "cxone-utils",
    "setHTMLAppState": "cxone-utils",
    # Basic nodes (explicit for completeness)
    "say": "@cognigy/basic-nodes",
    "code": "@cognigy/basic-nodes",
    "wait": "@cognigy/basic-nodes",
    "once": "@cognigy/basic-nodes",
    "goTo": "@cognigy/basic-nodes",
    "question": "@cognigy/basic-nodes",
    "httpRequest": "@cognigy/basic-nodes",
    "setContext": "@cognigy/basic-nodes",
    "ifThenElse": "@cognigy/basic-nodes",
    "lookup": "@cognigy/basic-nodes",
}


def _inject_extension(body: dict, dynamic_map: dict | None = None) -> dict:
    """Auto-inject extension for known node types if not already present.
    Checks static map first, then falls back to project-specific dynamic_map."""
    if "extension" in body or "type" not in body:
        return body
    node_type = body["type"]
    ext = _NODE_EXTENSION_MAP.get(node_type)
    if ext is None and dynamic_map:
        ext = dynamic_map.get(node_type)
    return {**body, "extension": ext} if ext else body


# ---------------------------------------------------------------------------
# P3 — Plural/singular resource_type normalisation
# ---------------------------------------------------------------------------

_RESOURCE_TYPE_ALIASES: dict[str, str] = {
    "project": "projects",
    "flow": "flows",
    "endpoint": "endpoints",
    "agent": "aiagents",
    "ai-agent": "aiagents",
    "aiagent": "aiagents",
    "knowledge-store": "knowledgestores",
    "knowledgestore": "knowledgestores",
    "function": "functions",
    "connection": "connections",
    "extension": "extensions",
    "locale": "locales",
    "lexicon": "lexicons",
    "snapshot": "snapshots",
    "playbook": "playbooks",
    "node": "node",  # node stays singular — it routes to chart path
    "nodes": "node",  # plural also routes to chart path, same as singular
}


def _normalise_rtype(rtype: str) -> str:
    return _RESOURCE_TYPE_ALIASES.get(rtype.lower(), rtype)


def _invoke_path(resource_type: str, resource_id: str, operation: str, body: dict, flow_id: str | None) -> str | None:
    if resource_type == "node" and operation == "move" and not flow_id:
        return None  # caller must check
    mapping = {
        ("node", "move"): f"/v2.0/flows/{flow_id}/chart/nodes/{resource_id}/move",
        ("flow", "clone"): f"/v2.0/flows/{resource_id}/clone",
        ("aiagent", "train"): f"/v2.0/aiagents/{resource_id}/train",
        ("sessions", "inject-context"): f"/v2.0/sessions/{resource_id}/context/inject",
        ("sessions", "inject-state"): f"/v2.0/sessions/{resource_id}/state/inject",
        ("sessions", "reset-context"): f"/v2.0/sessions/{resource_id}/context/reset",
        ("sessions", "reset-state"): f"/v2.0/sessions/{resource_id}/state/reset",
    }
    if resource_type == "knowledgestore" and operation == "run":
        connector_id = body.get("connector_id", "")
        return f"/v2.0/knowledgestores/{resource_id}/connectors/{connector_id}/run"
    return mapping.get(
        (resource_type, operation),
        f"/v2.0/{resource_type}/{resource_id}/{operation}",
    )


def _build_hierarchy(chart: dict) -> str:
    nodes = {n["_id"]: n for n in chart.get("nodes", [])}

    # Real Cognigy API format: {"node": "<nodeId>", "next": "<nextId>", "children": [...], "_id": "<relId>"}
    relations: dict[str, dict] = {}
    for r in chart.get("relations", []):
        node_id = r.get("node")
        if node_id:
            relations[node_id] = r

    def render(node_id: str, indent: int = 0, visited: frozenset = frozenset()) -> list[str]:
        if node_id in visited:
            return [f"{'  ' * indent}[CYCLE → {node_id}]"]
        visited = visited | {node_id}
        node = nodes.get(node_id, {})
        label = node.get("label") or node.get("type", node_id)
        ntype = node.get("type", "")
        prefix = "  " * indent
        lines = [f"{prefix}[{ntype}] {label} ({node_id})"]
        rel = relations.get(node_id, {})
        for child_id in rel.get("children", []):
            lines += render(child_id, indent + 1, visited)
        next_id = rel.get("next")
        if next_id:
            lines += render(next_id, indent, visited)
        return lines

    # Root nodes: not referenced as next or child by any other relation
    referenced: set[str] = set()
    for rel in relations.values():
        if rel.get("next"):
            referenced.add(rel["next"])
        for child_id in rel.get("children", []):
            referenced.add(child_id)

    roots = [node_id for node_id in relations if node_id not in referenced]
    # Fallback: pure cycle with no external entry point — start from any node so CYCLE is detected
    if not roots and relations:
        roots = [next(iter(relations))]
    lines: list[str] = []
    for root in roots:
        lines += render(root)
    return "\n".join(lines) if lines else "(empty chart)"


def _resource_path(resource_type: str, resource_id: str, flow_id: str | None = None) -> str | None:
    if resource_type == "node":
        if not flow_id:
            return None  # caller must check
        return f"/v2.0/flows/{flow_id}/chart/nodes/{resource_id}"
    return f"/v2.0/{resource_type}/{resource_id}"


def _api_error_response(exc: ApiError) -> list[TextContent]:
    return _ok({"error": "api_error", "status": exc.status_code, "detail": str(exc)})


def _unexpected_error_response(exc: Exception) -> list[TextContent]:
    return _ok({"error": "unexpected_error", "detail": str(exc)})


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _cognigy_get(args: dict) -> list[TextContent]:
        m, err = validate(CognigyGetArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        rid = m.resource_id
        cached, fresh = cache.get(rtype, rid)
        if fresh and cached:
            data = cached
            source = "cache"
        else:
            path = _resource_path(rtype, rid, m.flow_id)
            if path is None:
                return _ok({"error": "flow_id required when resource_type is 'node'"})
            try:
                data = client.get(path)
            except ApiError as exc:
                return _api_error_response(exc)
            except Exception as exc:
                return _unexpected_error_response(exc)
            cache.set(rtype, rid, data)
            source = "api"
        if m.fields:
            filtered = {k: data[k] for k in m.fields if k in data}
            if not filtered:
                return _ok({
                    "error": "none of the requested fields exist on this resource",
                    "requested_fields": m.fields,
                    "available_fields": sorted(strip_response(data).keys()),
                })
            data = filtered
        data = strip_response(data)
        return _ok({**data, "_source": source})

    def _cognigy_list(args: dict) -> list[TextContent]:
        m, err = validate(CognigyListArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        if rtype == "node":
            return _ok({
                "error": (
                    "Nodes cannot be listed independently — they exist only within a flow chart. "
                    "Use get_flow_chart(flow_id=<flowId>) to list all nodes in a flow."
                )
            })
        try:
            if m.agent_id:
                data = client.get(f"/v2.0/aiagents/{m.agent_id}/{rtype}", limit=m.limit)
            elif m.project_id:
                data = client.get(f"/v2.0/{rtype}", projectId=m.project_id, limit=m.limit)
            else:
                data = client.get(f"/v2.0/{rtype}", limit=m.limit)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        raw_items = data if isinstance(data, list) else data.get("items", [])
        if not m.full_objects:
            simplified = []
            for item in raw_items:
                entry = {"id": item.get("_id"), "name": item.get("name")}
                if "description" in item:
                    entry["description"] = item["description"]
                if "type" in item:
                    entry["type"] = item["type"]
                simplified.append(entry)
            result_data = {"items": simplified, "count": len(simplified)}
        else:
            result_data = data if not isinstance(data, list) else {"items": data, "count": len(data)}
        if m.fields:
            items = result_data.get("items", [])
            available = {k for item in items for k in item.keys()}
            if items and not (set(m.fields) & available):
                stripped_available = {k for item in items for k in strip_response(item).keys()}
                return _ok({
                    "error": "none of the requested fields exist on any item in this list",
                    "requested_fields": m.fields,
                    "available_fields": sorted(stripped_available),
                })
            filtered = [{k: item[k] for k in m.fields if k in item} for item in items]
            result_data = {"items": filtered, "count": len(filtered)}
        if m.full_objects:
            items = result_data.get("items", [])
            result_data = {**result_data, "items": [strip_response(item) for item in items]}
        return _ok(result_data)

    def _cognigy_create(args: dict) -> list[TextContent]:
        m, err = validate(CognigyCreateArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        body = m.body
        if rtype == "node":
            if not m.flow_id:
                return _ok({"error": "flow_id required to create a node"})
            if body.get("type") == "code":
                return _ok({"error": (
                    "Code nodes must be created via push_code_node "
                    "(provides file-backed conflict detection). "
                    "To create a new code node: push_code_node(script_file=..., flow_id=..., mode=..., target=...). "
                    'See explain("tool-selection") for guidance.'
                )})
            if body.get("type") == "aiAgentJobTool":
                return _ok({"error": (
                    "AI Agent tool nodes must be created via push_agent_tool "
                    "(file-backed, maps .tool.json spec to Cognigy config). "
                    "To create a new tool: push_agent_tool(tool_file=..., flow_id=..., job_node_id=...). "
                    'See explain("tool-selection") for guidance.'
                )})
            valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
            if "mode" in body and body["mode"] not in valid_modes:
                return _ok({
                    "error": (
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (child of container, aiAgentJobTool only), '
                        f'append (sibling after target — also correct for Once/IF branches: target the branch marker _id), '
                        f'insertAfter (may return 500 on AU1 — prefer append), '
                        f'insertBefore (may return 500 on AU1 — prefer append).'
                    )
                })
            if body.get("type") == "say" and "config" in body:
                body = {**body, "config": _normalise_say_config(body["config"])}
            if body.get("type") == "aiAgentToolAnswer" and "config" in body:
                body = {**body, "config": _normalise_answer_config(body["config"])}
            body = _inject_extension(body, state.get("extension_map") or {})
            path = f"/v2.0/flows/{m.flow_id}/chart/nodes"
        else:
            path = f"/v2.0/{rtype}"
        try:
            result = client.post(path, body)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        resource_id = result.get("_id") or result.get("id")
        name = result.get("name") or result.get("label")
        if name and resource_id:
            if rtype == "node":
                state.set("nodes", name, value={"id": resource_id, "flowId": m.flow_id})
            else:
                state.set(rtype, name, value={"id": resource_id})
        if resource_id:
            cache.set(rtype, resource_id, result)
        if m.return_full_object:
            return _ok(strip_response(result))
        minimal = {
            "_id": result.get("_id"),
            "referenceId": result.get("referenceId"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})

    def _cognigy_update(args: dict) -> list[TextContent]:
        m, err = validate(CognigyUpdateArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        body = m.body
        path = _resource_path(rtype, m.resource_id, m.flow_id)
        if path is None:
            return _ok({"error": "flow_id required when resource_type is 'node'"})
        if rtype == "node" and "mode" in body:
            valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
            if body["mode"] not in valid_modes:
                return _ok({
                    "error": (
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (child of container, aiAgentJobTool only), '
                        f'append (sibling after target — also correct for Once/IF branches: target the branch marker _id), '
                        f'insertAfter (may return 500 on AU1 — prefer append), '
                        f'insertBefore (may return 500 on AU1 — prefer append).'
                    )
                })
        try:
            current = client.get(path)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        if rtype == "node" and current.get("type") == "code":
            return _ok({"error": (
                "Code nodes must be updated via push_code_node "
                "(provides file-backed conflict detection). "
                'See explain("tool-selection") for guidance.'
            )})
        if current.get("type") == "say" and "config" in body:
            body = {**body, "config": _normalise_say_config(body["config"])}
        if current.get("type") == "aiAgentToolAnswer" and "config" in body:
            body = {**body, "config": _normalise_answer_config(body["config"])}
        if m.merge_config and "config" in body and "config" in current:
            current_config = {k: v for k, v in current["config"].items() if k not in BLOCKED_IN_CONFIG}
            merged = _deep_merge(current_config, body["config"])
            body = {**body, "config": merged}
        try:
            result = client.patch(path, body)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        cache.set(rtype, m.resource_id, result)
        if m.return_full_object:
            return _ok(strip_response(result))
        minimal = {
            "_id": result.get("_id"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})

    def _cognigy_delete(args: dict) -> list[TextContent]:
        m, err = validate(CognigyDeleteArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        path = _resource_path(rtype, m.resource_id, m.flow_id)
        if path is None:
            return _ok({"error": "flow_id required when resource_type is 'node'"})
        try:
            result = client.delete(path)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        cache.invalidate(rtype, m.resource_id)
        return _ok({"deleted": True, "resource_id": m.resource_id, **result})

    def _cognigy_invoke(args: dict) -> list[TextContent]:
        m, err = validate(CognigyInvokeArgs, args)
        if err:
            return err
        rtype = "node" if m.resource_type.lower() in ("node", "nodes") else m.resource_type
        path = _invoke_path(rtype, m.resource_id, m.operation, m.body, m.flow_id)
        if path is None:
            return _ok({"error": f"flow_id required for {rtype}/{m.operation}"})
        try:
            result = client.post(path, m.body)
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        return _ok(strip_response(result))

    def _get_flow_chart(args: dict) -> list[TextContent]:
        m, err = validate(GetFlowChartArgs, args)
        if err:
            return err
        try:
            chart = client.get(f"/v2.0/flows/{m.flow_id}/chart")
        except ApiError as exc:
            return _api_error_response(exc)
        except Exception as exc:
            return _unexpected_error_response(exc)
        stripped_nodes = [strip_response(n) for n in chart.get("nodes", [])]
        if m.format == "hierarchy":
            stripped_chart = {**chart, "nodes": stripped_nodes}
            hierarchy = _build_hierarchy(stripped_chart)
            return _ok({"hierarchy": hierarchy})
        elif m.format == "raw":
            return _ok({
                "nodes": stripped_nodes,
                "relations": chart.get("relations", []),
            })
        else:
            stripped_chart = {**chart, "nodes": stripped_nodes}
            hierarchy = _build_hierarchy(stripped_chart)
            return _ok({
                "relations": chart.get("relations", []),
                "nodes": stripped_nodes,
                "hierarchy": hierarchy,
            })

    return {
        "cognigy_get": _cognigy_get,
        "cognigy_list": _cognigy_list,
        "cognigy_create": _cognigy_create,
        "cognigy_update": _cognigy_update,
        "cognigy_delete": _cognigy_delete,
        "cognigy_invoke": _cognigy_invoke,
        "get_flow_chart": _get_flow_chart,
    }
