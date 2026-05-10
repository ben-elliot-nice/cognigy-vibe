from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="sync_remote_state",
        description="Hard reset: wipe local cache and repopulate from Cognigy remote. "
                    "Runs automatically after session idle > threshold. Call manually "
                    "after making changes in the Cognigy UI.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Cognigy project ID"},
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="get_build_state",
        description="Return the current .state.json — all known name→ID mappings for "
                    "flows, agents, endpoints, tools. Use resolve_resource for single lookups.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="resolve_resource",
        description="Fast lookup of a Cognigy resource ID by friendly name from .state.json. "
                    "No API call. Returns the full state entry for that resource.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "resource_type": {
                    "type": "string",
                    "description": "One of: flows, agents, endpoints, tools, nodes, jobs",
                },
            },
            "required": ["name", "resource_type"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def make_handlers(
    client: CognigyClient, state: ProjectState, cache: Cache
) -> dict:
    def _sync_remote_state(args: dict) -> list[TextContent]:
        project_id = args["project_id"]
        cache.invalidate_all()
        errors: list[str] = []

        # Flows
        try:
            flows_resp = client.get(f"/v2.0/projects/{project_id}/flows", limit=100)
            flows = flows_resp.get("items", [])
        except Exception as exc:
            errors.append(f"flows: {exc}")
            flows = []

        for flow in flows:
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)

        # Chart-based tool discovery (non-fatal per flow)
        for flow in flows:
            try:
                chart = client.get(f"/v2.0/flows/{flow['_id']}/chart")
                for node in chart.get("nodes", []):
                    if node.get("type") == "aiAgentJobTool":
                        label = node.get("label", node["_id"])
                        state.set("tools", label, value={
                            "id": node["_id"],
                            "flowId": flow["_id"],
                            "flowName": flow["name"],
                        })
            except Exception:
                pass  # chart unavailable — skip tool discovery for this flow

        # Agents
        try:
            agents_resp = client.get(f"/v2.0/projects/{project_id}/aiagents", limit=100)
            for agent in agents_resp.get("items", []):
                state.set("agents", agent["name"], value={"id": agent["_id"]})
                cache.set("aiagents", agent["_id"], agent)
        except Exception as exc:
            errors.append(f"agents: {exc}")

        # Endpoints
        try:
            eps_resp = client.get(f"/v2.0/projects/{project_id}/endpoints", limit=100)
            for ep in eps_resp.get("items", []):
                state.set("endpoints", ep["name"], value={
                    "id": ep["_id"],
                    "urlToken": ep.get("urlToken", ""),
                    "flowReferenceId": ep.get("flowReferenceId", ""),
                })
                cache.set("endpoints", ep["_id"], ep)
        except Exception as exc:
            errors.append(f"endpoints: {exc}")

        state.touch_interaction()
        result: dict = {"synced": True, "project_id": project_id}
        if errors:
            result["errors"] = errors
        return _ok(result)

    def _get_build_state(_args: dict) -> list[TextContent]:
        return _ok(state.as_dict())

    def _resolve_resource(args: dict) -> list[TextContent]:
        name = args["name"]
        rtype = args["resource_type"]
        entry = state.get(rtype, name)
        if entry is None:
            return _ok({"error": f"'{name}' not found in {rtype}"})
        return _ok(entry)

    return {
        "sync_remote_state": _sync_remote_state,
        "get_build_state": _get_build_state,
        "resolve_resource": _resolve_resource,
    }
