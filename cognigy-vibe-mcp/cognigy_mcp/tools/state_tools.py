from __future__ import annotations
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


class SetProjectGenerativeAISettingsArgs(BaseModel):
    project_id: str = Field(description="Cognigy project _id to configure")
    use_case_settings: dict[str, str] = Field(
        description="Map of Generative AI use-case key (e.g. 'aiAgent', 'knowledgeSearch') "
                     "to the target LLM's MongoDB _id"
    )


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

GENERATION_USE_CASES: list[str] = [
    "aiAgent", "gptPromptNode", "aiEnhancedOutputs", "sentimentAnalysis",
    "designTimeGeneration", "answerExtraction", "conversationAnalyzer",
]
KNOWLEDGE_USE_CASE = "knowledgeSearch"
_KNOWN_USE_CASES = frozenset(GENERATION_USE_CASES) | {KNOWLEDGE_USE_CASE}


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
            "Use after creating the agent resource (cognigy_create(resource_type=\"aiagents\", ...)) to ensure the new project can use an org-level LLM. "
            "Errors if the LLM is project-scoped (use manage_packages instead) or not found."
        ),
        inputSchema=make_schema(AssignOrgLlmArgs),
    ),
    Tool(
        name="set_project_generative_ai_settings",
        description=(
            "Set which LLM a project uses for each Cognigy Generative AI use-case via a "
            "project-level settings PATCH. This is what actually activates a model for these "
            "platform features — assigning an LLM to a project via assign_org_llm alone does not. "
            "Partial PATCH is safe: only the use-cases passed in use_case_settings are touched, "
            "others are left untouched. Allowed use_case_settings keys: "
            f"{', '.join(sorted(_KNOWN_USE_CASES))} — an unrecognised key returns an "
            "unknown_use_case error instead of being sent to the API. use_case_settings must be "
            "non-empty."
        ),
        inputSchema=make_schema(SetProjectGenerativeAISettingsArgs),
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
            for ext_summary in exts_resp.get("items", []):
                ext_id = ext_summary["_id"]
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

        if flows:
            try:
                descriptors_resp = client.get(f"/v2.0/flows/{flows[0]['_id']}/chart/descriptors")
                marker_types = {
                    d["type"] for d in descriptors_resp.get("items", [])
                    if d.get("type") and d.get("parentType")
                }
                state.set("branch_marker_types", value=sorted(marker_types))
            except Exception as exc:
                errors.append(f"chart_descriptors: {exc}")

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
        project_id = state.project_id or os.getenv("COGNIGY_PROJECT_ID", "").strip() or None
        config_fields: dict = {
            "_version": pkg_version("cognigy-vibe-mcp"),
            "config_loaded": build_config is not None,
            "project_id": project_id,
            "state_source": str(state.config_dir) if project_id else None,
        }
        if not project_id:
            return _ok({
                **config_fields,
                "error": "no_project_bound",
                "hint": "Call sync_remote_state(project_id=<id>) first, or set COGNIGY_PROJECT_ID in your .env",
            })
        if build_config is not None:
            config_fields["config_source"] = config_source or ""
            config_fields["config_summary"] = _make_config_summary(build_config)
        full_state = state.as_dict()
        if m.resource_type:
            filtered = full_state.get(m.resource_type, {})
            return _ok({m.resource_type: filtered, "_filtered": True, **config_fields})
        return _ok({**full_state, **config_fields})

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

    def _set_project_generative_ai_settings(args: dict) -> list[TextContent]:
        m, err = validate(SetProjectGenerativeAISettingsArgs, args)
        if err:
            return err
        if not m.use_case_settings:
            return _ok({
                "error": "empty_use_case_settings",
                "hint": "use_case_settings must contain at least one use-case key",
            })
        unknown_keys = [k for k in m.use_case_settings if k not in _KNOWN_USE_CASES]
        if unknown_keys:
            return _ok({
                "error": "unknown_use_case",
                "unknown_keys": unknown_keys,
                "allowed_keys": sorted(_KNOWN_USE_CASES),
            })
        body = {
            "generativeAISettings": {
                "useCasesSettings": {
                    key: {"largeLanguageModelId": llm_id}
                    for key, llm_id in m.use_case_settings.items()
                }
            }
        }
        try:
            client.patch(f"/v2.0/projects/{m.project_id}/settings", body)
        except ApiError as exc:
            return _ok({"error": "patch_failed", "status": exc.status_code, "detail": str(exc)})
        except Exception as exc:
            return _ok({"error": "patch_failed", "detail": str(exc)})
        return _ok({
            "updated": True,
            "project_id": m.project_id,
            "use_cases": list(m.use_case_settings),
        })

    return {
        "sync_remote_state": _sync_remote_state,
        "get_build_state": _get_build_state,
        "resolve_resource": _resolve_resource,
        "assign_org_llm": _assign_org_llm,
        "set_project_generative_ai_settings": _set_project_generative_ai_settings,
    }
