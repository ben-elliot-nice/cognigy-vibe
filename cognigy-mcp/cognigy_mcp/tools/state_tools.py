from __future__ import annotations
import json
import os
from importlib.metadata import version as pkg_version
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class SyncRemoteStateArgs(BaseModel):
    project_id: str | None = Field(
        None,
        description="Cognigy project ID. Optional if COGNIGY_PROJECT_ID is set in environment.",
    )


class GetBuildStateArgs(BaseModel):
    resource_type: str | None = Field(
        None,
        description="Filter to one resource category: flows, agents, endpoints, tools, nodes, jobs",
    )


class ResolveResourceArgs(BaseModel):
    name: str
    resource_type: str = Field(description="One of: flows, agents, endpoints, tools, nodes, jobs")


class AssignOrgLlmArgs(BaseModel):
    project_id: str = Field(description="Cognigy project _id to assign the LLM to")
    llm_id: str = Field(description="MongoDB _id of the org-level LLM (not referenceId)")


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
        inputSchema=make_schema(SyncRemoteStateArgs),
    ),
    Tool(
        name="get_build_state",
        description="Return the current .state.json — all known name to ID mappings. "
                    "Pass resource_type to scope the response and avoid context overflow on large projects. "
                    "Example: get_build_state(resource_type='flows') returns ~50 tokens vs ~500 for full state. "
                    "Filter values: flows, agents, endpoints, tools, nodes, jobs.",
        inputSchema=make_schema(GetBuildStateArgs),
    ),
    Tool(
        name="resolve_resource",
        description="Fast lookup of a Cognigy resource ID by friendly name from .state.json. "
                    "No API call. Returns the full state entry for that resource.",
        inputSchema=make_schema(ResolveResourceArgs),
    ),
    Tool(
        name="assign_org_llm",
        description=(
            "Append a project to an organisation-level LLM's assignedToProjects list. "
            "Safe and idempotent — if the project is already assigned, no write is made. "
            "Use after create_ai_agent to ensure the new project can use an org-level LLM. "
            "Errors if the LLM is project-scoped (use manage_packages instead) or not found."
        ),
        inputSchema=make_schema(AssignOrgLlmArgs),
    ),
]


def _make_config_summary(config: dict) -> dict:
    return {
        "region": config.get("connection", {}).get("region", ""),
        "llm_default": config.get("llm", {}).get("default", ""),
        "tts_label": config.get("tts", {}).get("label", ""),
        "stt_label": config.get("stt", {}).get("label", ""),
        "locale": config.get("locale", ""),
    }


def make_handlers(
    client: CognigyClient,
    state: ProjectState,
    cache: Cache,
    build_config: "dict | None" = None,
    config_source: "str | None" = None,
) -> dict:
    def _sync_remote_state(args: dict) -> list[TextContent]:
        m, err = validate(SyncRemoteStateArgs, args)
        if err:
            return err
        project_id = m.project_id or os.getenv("COGNIGY_PROJECT_ID", "").strip() or None

        if not project_id:
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

        _write_to_dotenv("COGNIGY_PROJECT_ID", project_id)
        state.bind_project(project_id)
        cache.invalidate_all()
        errors: list[str] = []

        flows: list = []
        try:
            flows_resp = client.get("/v2.0/flows", projectId=project_id, limit=100)
            flows = flows_resp.get("items", [])
        except Exception as exc:
            errors.append(f"flows: {exc}")

        for flow in flows:
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)

        ext_map: dict[str, str] = {}
        try:
            exts_resp = client.get("/v2.0/extensions", projectId=project_id, limit=100)
            for ext_summary in exts_resp.get("_embedded", {}).get("extensions", []):
                ext_id = ext_summary["_links"]["self"]["href"].split("/")[-1]
                ext_name = ext_summary["name"]
                try:
                    ext_detail = client.get(f"/v2.0/extensions/{ext_id}")
                    for node_def in ext_detail.get("nodes", []):
                        ext_map[node_def["type"]] = ext_name
                except Exception:
                    pass
        except Exception as exc:
            errors.append(f"extensions: {exc}")
        state.set("extension_map", value=ext_map)

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
                        try:
                            agent_resource = client.get(f"/v2.0/aiagents/{agent['_id']}")
                            cache.set("aiagents", agent["_id"], agent_resource)
                            state.set("agents", agent_resource.get("name", agent.get("name", agent["_id"])), value={"id": agent["_id"]})
                        except Exception:
                            state.set("agents", agent.get("name", agent["_id"]), value={"id": agent["_id"]})
            except Exception:
                pass

        try:
            eps_resp = client.get("/v2.0/endpoints", projectId=project_id, limit=100)
            for ep in eps_resp.get("items", []):
                state.set("endpoints", ep["name"], value={
                    "id": ep["_id"],
                    "urlToken": ep.get("URLToken") or ep.get("urlToken", ""),
                    "flowReferenceId": ep.get("flowId") or ep.get("flowReferenceId", ""),
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
        m, err = validate(GetBuildStateArgs, args)
        if err:
            return err
        full_state = state.as_dict()
        config_fields: dict = {"config_loaded": build_config is not None}
        if build_config is not None:
            config_fields["config_source"] = config_source or ""
            config_fields["config_summary"] = _make_config_summary(build_config)
        if m.resource_type:
            filtered = full_state.get(m.resource_type, {})
            return _ok({m.resource_type: filtered, "_filtered": True, **config_fields})
        return _ok({**full_state, "_version": pkg_version("cognigy-vibe-mcp"), **config_fields})

    def _resolve_resource(args: dict) -> list[TextContent]:
        m, err = validate(ResolveResourceArgs, args)
        if err:
            return err
        entry = state.get(m.resource_type, m.name)
        if entry is None:
            return _ok({"error": f"'{m.name}' not found in {m.resource_type}"})
        return _ok(entry)

    def _assign_org_llm(args: dict) -> list[TextContent]:
        m, err = validate(AssignOrgLlmArgs, args)
        if err:
            return err
        try:
            llm = client.get(f"/v2.0/largelanguagemodels/{m.llm_id}")
        except ApiError as exc:
            if exc.status_code == 404:
                return _ok({"error": "llm_not_found", "llm_id": m.llm_id})
            return _ok({"error": "get_failed", "status": exc.status_code, "detail": str(exc)})
        except Exception as exc:
            return _ok({"error": "get_failed", "detail": str(exc)})
        if llm.get("resourceLevel") != "organisation":
            return _ok({
                "error": "not_org_level",
                "hint": "Use manage_packages to import a project-scoped LLM instead",
            })
        assigned: list = llm.get("assignedToProjects") or []
        if m.project_id in assigned:
            return _ok({"already_assigned": True, "llm_name": llm.get("name", "")})
        try:
            client.patch(
                f"/v2.0/largelanguagemodels/{m.llm_id}",
                {"assignedToProjects": assigned + [m.project_id]},
            )
        except ApiError as exc:
            return _ok({"error": "patch_failed", "status": exc.status_code, "detail": str(exc)})
        except Exception as exc:
            return _ok({"error": "patch_failed", "detail": str(exc)})
        return _ok({"assigned": True, "llm_name": llm.get("name", ""), "project_id": m.project_id})

    return {
        "sync_remote_state": _sync_remote_state,
        "get_build_state": _get_build_state,
        "resolve_resource": _resolve_resource,
        "assign_org_llm": _assign_org_llm,
    }
