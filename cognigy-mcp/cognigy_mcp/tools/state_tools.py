from __future__ import annotations
import json
import os
from importlib.metadata import version as pkg_version
from pathlib import Path
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


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
}


def _normalise_rtype(rtype: str) -> str:
    return _RESOURCE_TYPE_ALIASES.get(rtype.lower(), rtype)


def _write_to_dotenv(key: str, value: str) -> None:
    """Append key=value to .env in CWD if the key is not already present."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return  # don't create .env from scratch
    content = env_path.read_text()
    if key in content:
        return
    env_path.write_text(content.rstrip("\n") + f"\n{key}={value}\n")

TOOLS: list[Tool] = [
    Tool(
        name="sync_remote_state",
        description="Hard reset: wipe local cache and repopulate from Cognigy remote. "
                    "Runs automatically after session idle > threshold. Call manually "
                    "after making changes in the Cognigy UI.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Cognigy project ID. Optional if COGNIGY_PROJECT_ID is set in environment.",
                },
            },
        },
    ),
    Tool(
        name="get_build_state",
        description="Return the current .state.json — all known name→ID mappings. "
                    "Pass resource_type to scope the response and avoid context overflow on large projects.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "Filter to one resource category: flows, agents, endpoints, tools, nodes, jobs",
                },
            },
        },
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
        project_id = args.get("project_id") or os.getenv("COGNIGY_PROJECT_ID", "").strip() or None

        if not project_id:
            # List projects to help the agent pick one
            try:
                projects_resp = client.get("/v2.0/projects")
                projects = [{"id": p["_id"], "name": p["name"]} for p in projects_resp.get("items", [])]
            except Exception:
                projects = []
            return _ok({
                "error": "project_id is required",
                "hint": "Pass project_id=<id>, or set COGNIGY_PROJECT_ID=<id> in your .env file",
                "available_projects": projects,
            })

        # Write to .env if not already there
        _write_to_dotenv("COGNIGY_PROJECT_ID", project_id)

        # Bind the live state instance to this project so the rest of this session
        # is scoped correctly (no restart required).
        state.bind_project(project_id)

        cache.invalidate_all()
        errors: list[str] = []

        # Flows — projectId is a query param
        flows: list = []
        try:
            flows_resp = client.get("/v2.0/flows", projectId=project_id, limit=100)
            flows = flows_resp.get("items", [])
        except Exception as exc:
            errors.append(f"flows: {exc}")

        for flow in flows:
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)

        # Per-flow discovery: aiAgentJobTool nodes + AI Agent definitions
        seen_agents: set = set()
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
                pass
            try:
                agents_resp = client.get(f"/v2.0/flows/{flow['_id']}/chart/nodes/aiagents")
                for agent in agents_resp.get("items", []):
                    if agent["_id"] not in seen_agents:
                        seen_agents.add(agent["_id"])
                        state.set("agents", agent["name"], value={"id": agent["_id"]})
                        cache.set("aiagents", agent["_id"], agent)
            except Exception:
                pass

        # Endpoints — projectId is a query param
        try:
            eps_resp = client.get("/v2.0/endpoints", projectId=project_id, limit=100)
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

    def _get_build_state(args: dict) -> list[TextContent]:
        resource_type = args.get("resource_type")
        full_state = state.as_dict()
        if resource_type:
            filtered = full_state.get(resource_type, {})
            return _ok({resource_type: filtered, "_filtered": True})
        return _ok({**full_state, "_version": pkg_version("cognigy-vibe-mcp")})

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
