from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="cognigy_get",
        description="GET any Cognigy resource by ID. Cache-first (5-min TTL). "
                    "Response includes _source: 'cache' or 'api'.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "e.g. flows, aiagents, endpoints"},
                "resource_id": {"type": "string"},
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id"],
        },
    ),
    Tool(
        name="cognigy_list",
        description="List Cognigy resources. Pass project_id for project-scoped resources, "
                    "agent_id for agent-scoped resources (e.g. listing jobs).",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "project_id": {"type": "string"},
                "agent_id": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["resource_type"],
        },
    ),
    Tool(
        name="cognigy_create",
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include flowId, type, mode, target.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "body": {"type": "object"},
                "flow_id": {"type": "string", "description": "Required when creating nodes"},
            },
            "required": ["resource_type", "body"],
        },
    ),
    Tool(
        name="cognigy_update",
        description="PATCH a Cognigy resource. WARNING: Cognigy PATCH is full-replace on 'config' — "
                    "set merge_config=true to deep-merge instead of overwriting. Always use merge_config=true "
                    "for partial config updates.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "body": {"type": "object"},
                "merge_config": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, deep-merges body.config with current config rather than replacing",
                },
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id", "body"],
        },
    ),
    Tool(
        name="cognigy_delete",
        description="DELETE a Cognigy resource. For nodes, pass flow_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id"],
        },
    ),
    Tool(
        name="cognigy_invoke",
        description="Run a named operation on a Cognigy resource. "
                    "Operations: node/move, flow/clone, aiagent/train, "
                    "knowledgestore/run, sessions/inject-context, sessions/inject-state.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "operation": {"type": "string"},
                "body": {"type": "object", "default": {}},
                "flow_id": {"type": "string", "description": "Required for node operations"},
            },
            "required": ["resource_type", "resource_id", "operation"],
        },
    ),
    Tool(
        name="get_flow_chart",
        description="Fetch the full chart for a flow. Returns both the raw relations array and "
                    "a human-readable hierarchy string for quick orientation.",
        inputSchema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string"},
            },
            "required": ["flow_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _invoke_path(resource_type: str, resource_id: str, operation: str, body: dict, flow_id: str | None) -> str:
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
    relations = {r["nodeId"]: r for r in chart.get("relations", [])}

    def render(node_id: str, indent: int = 0) -> list[str]:
        node = nodes.get(node_id, {})
        label = node.get("label") or node.get("type", node_id)
        ntype = node.get("type", "")
        prefix = "  " * indent
        lines = [f"{prefix}[{ntype}] {label} ({node_id})"]
        rel = relations.get(node_id, {})
        for child_id in rel.get("childIds", []):
            lines += render(child_id, indent + 1)
        next_id = rel.get("nextId")
        if next_id:
            lines += render(next_id, indent)
        return lines

    # Find root: node with no parent and no previous
    roots = [
        nid for nid, rel in relations.items()
        if not rel.get("parentId") and not rel.get("previousId")
    ]
    lines = []
    for root in roots:
        lines += render(root)
    return "\n".join(lines) if lines else "(empty chart)"


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _cognigy_get(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        flow_id = args.get("flow_id")
        cached, fresh = cache.get(rtype, rid)
        if fresh and cached:
            return _ok({**cached, "_source": "cache"})
        if rtype == "node":
            data = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{rid}")
        else:
            data = client.get(f"/v2.0/{rtype}/{rid}")
        cache.set(rtype, rid, data)
        return _ok({**data, "_source": "api"})

    def _cognigy_list(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        project_id = args.get("project_id")
        agent_id = args.get("agent_id")
        limit = args.get("limit", 100)
        if agent_id:
            path = f"/v2.0/aiagents/{agent_id}/{rtype}"
        elif project_id:
            path = f"/v2.0/projects/{project_id}/{rtype}"
        else:
            path = f"/v2.0/{rtype}"
        data = client.get(path, limit=limit)
        return _ok(data)

    def _cognigy_create(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        body = args["body"]
        flow_id = args.get("flow_id")
        if rtype == "node":
            if not flow_id:
                raise ValueError("flow_id required to create a node")
            path = f"/v2.0/flows/{flow_id}/chart/nodes"
        else:
            path = f"/v2.0/{rtype}"
        result = client.post(path, body)
        # Auto-save to state
        name = result.get("name") or result.get("label")
        if name:
            state.set(rtype, name, value={"id": result["_id"]})
        cache.set(rtype, result["_id"], result)
        return _ok(result)

    def _cognigy_update(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        body = args["body"]
        merge_config = args.get("merge_config", False)
        flow_id = args.get("flow_id")

        if rtype == "node":
            path = f"/v2.0/flows/{flow_id}/chart/nodes/{rid}"
        else:
            path = f"/v2.0/{rtype}/{rid}"

        # Always fetch fresh state before writing
        current = client.get(path)

        if merge_config and "config" in body and "config" in current:
            merged = {**current["config"], **body["config"]}
            body = {**body, "config": merged}

        result = client.patch(path, body)
        cache.set(rtype, rid, result)
        return _ok(result)

    def _cognigy_delete(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        flow_id = args.get("flow_id")
        if rtype == "node":
            path = f"/v2.0/flows/{flow_id}/chart/nodes/{rid}"
        else:
            path = f"/v2.0/{rtype}/{rid}"
        result = client.delete(path)
        cache.invalidate(rtype, rid)
        return _ok({"deleted": True, "resource_id": rid, **result})

    def _cognigy_invoke(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        operation = args["operation"]
        body = args.get("body", {})
        flow_id = args.get("flow_id")
        path = _invoke_path(rtype, rid, operation, body, flow_id)
        result = client.post(path, body)
        return _ok(result)

    def _get_flow_chart(args: dict) -> list[TextContent]:
        flow_id = args["flow_id"]
        chart = client.get(f"/v2.0/flows/{flow_id}/chart")
        hierarchy = _build_hierarchy(chart)
        return _ok({"relations": chart.get("relations", []), "nodes": chart.get("nodes", []), "hierarchy": hierarchy})

    return {
        "cognigy_get": _cognigy_get,
        "cognigy_list": _cognigy_list,
        "cognigy_create": _cognigy_create,
        "cognigy_update": _cognigy_update,
        "cognigy_delete": _cognigy_delete,
        "cognigy_invoke": _cognigy_invoke,
        "get_flow_chart": _get_flow_chart,
    }
