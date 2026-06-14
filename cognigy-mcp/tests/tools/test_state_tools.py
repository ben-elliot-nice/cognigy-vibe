import json
import pytest
from cognigy_mcp.tools.state_tools import make_handlers, TOOLS
from cognigy_mcp.tools.flow_ops import make_handlers as flow_make_handlers


def test_tools_exported():
    names = [t.name for t in TOOLS]
    assert "sync_remote_state" in names
    assert "get_build_state" in names
    assert "resolve_resource" in names


def test_get_build_state_returns_state(mock_client, state, cache):
    state.set("flows", "Main", value={"id": "flow-1"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_build_state"]({})
    data = json.loads(result[0].text)
    assert data["flows"]["Main"]["id"] == "flow-1"


def test_resolve_resource_found(mock_client, state, cache):
    state.set("flows", "Main", value={"id": "flow-1"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["resolve_resource"]({"name": "Main", "resource_type": "flows"})
    data = json.loads(result[0].text)
    assert data["id"] == "flow-1"


def test_resolve_resource_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["resolve_resource"]({"name": "Missing", "resource_type": "flows"})
    data = json.loads(result[0].text)
    assert "not found" in data.get("error", "").lower()


def test_sync_remote_state_calls_api(mock_client, state, cache):
    project_id = state.project_id
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},                                     # GET /v2.0/flows?projectId=...
        {"_embedded": {"extensions": []}},                                                        # GET /v2.0/extensions?projectId=...
        {"nodes": []},                                                                            # chart (tool discovery)
        {"items": [{"_id": "agent-1", "name": "My Agent"}]},                                     # chart/nodes/aiagents
        {"_id": "agent-1", "name": "My Agent", "speakingStyle": "formal"},                       # GET /v2.0/aiagents/agent-1
        {"items": [{"_id": "ep-1", "name": "REST", "URLToken": "tok123", "flowId": "flow-1"}]},  # GET /v2.0/endpoints?projectId=...
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data.get("synced") is True
    assert state.get("flows", "Main Flow", "id") == "flow-1"
    assert state.get("agents", "My Agent", "id") == "agent-1"


def test_sync_remote_state_caches_canonical_aiagent_resource(mock_client, state, cache):
    """sync_remote_state must cache the canonical AI Agent resource, not chart-node data.

    The chart/nodes/aiagents endpoint returns hybrid objects with chart-node fields
    (nodeId, config.name, type: "aiAgentJob"). Caching these directly causes
    cognigy_get to return node config instead of the agent resource (issue #22).
    After the fix, sync must fetch /v2.0/aiagents/{id} and cache that instead.
    """
    project_id = state.project_id
    chart_node_data = {
        "_id": "agent-1",
        "type": "aiAgentJob",
        "nodeId": "node-abc",
        "config": {"name": "My Agent", "instructions": "be helpful"},
    }
    canonical_resource = {
        "_id": "agent-1",
        "name": "My Agent",
        "description": "A helpful agent",
        "speakingStyle": "formal",
        "knowledgeReferenceId": "ks-xyz",
    }
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows
        {"_embedded": {"extensions": []}},                      # extensions
        {"nodes": []},                                          # chart (tool discovery)
        {"items": [chart_node_data]},                           # chart/nodes/aiagents
        canonical_resource,                                     # /v2.0/aiagents/agent-1
        {"items": []},                                          # endpoints
    ]
    handlers = make_handlers(mock_client, state, cache)
    handlers["sync_remote_state"]({"project_id": project_id})

    cached, fresh = cache.get("aiagents", "agent-1")
    assert fresh, "Cache entry should be fresh after sync"
    assert cached is not None, "Cache entry should exist for agent-1"
    assert "speakingStyle" in cached, (
        f"Cached data must be canonical AI Agent resource, not chart-node data. Got: {cached}"
    )
    assert "nodeId" not in cached, (
        f"Cache must not contain chart-node fields (nodeId). Got: {cached}"
    )


def test_sync_handles_list_failure_gracefully(mock_client, state, cache):
    """sync_remote_state returns synced=True even if flows, extensions, or endpoints fail."""
    project_id = state.project_id
    mock_client.get.side_effect = [
        Exception("API unavailable"),  # GET /v2.0/flows?projectId=... FAIL
        Exception("API unavailable"),  # GET /v2.0/extensions?projectId=... FAIL
        Exception("API unavailable"),  # GET /v2.0/endpoints?projectId=... FAIL
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data["synced"] is True
    assert "errors" in data
    assert any("flows" in e for e in data["errors"])


def test_cognigy_list_uses_projectId_query_param(mock_client, state, cache):
    """cognigy_list with project_id must pass projectId as a query param, not a path segment."""
    mock_client.get.return_value = {"items": [{"_id": "f1", "name": "My Flow"}]}
    handlers = flow_make_handlers(mock_client, state, cache)
    handlers["cognigy_list"]({"resource_type": "flows", "project_id": "proj-1"})
    call_path = mock_client.get.call_args[0][0]
    call_kwargs = mock_client.get.call_args[1]
    assert call_path == "/v2.0/flows"
    assert call_kwargs.get("projectId") == "proj-1"


def test_sync_no_project_id_lists_projects(mock_client, state, cache):
    """Missing project_id should list projects and return helpful error."""
    mock_client.get.return_value = {"items": [{"_id": "p1", "name": "Demo Project"}]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({})
    data = json.loads(result[0].text)
    assert "error" in data
    assert data.get("available_projects")
    assert data["available_projects"][0]["id"] == "p1"


def test_get_build_state_filtered(mock_client, state, cache):
    """resource_type filter should return only that section of state."""
    state.set("flows", "Main", value={"id": "flow-1"})
    state.set("agents", "Vera", value={"id": "agent-1"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_build_state"]({"resource_type": "flows"})
    data = json.loads(result[0].text)
    assert "flows" in data
    assert "agents" not in data
    assert data["flows"]["Main"]["id"] == "flow-1"


def test_sync_remote_state_binds_project_in_session(mock_client, cache, tmp_path, monkeypatch):
    """sync_remote_state must call bind_project so state.project_id is set for the rest of the session."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    from cognigy_mcp.state import ProjectState
    unscoped = ProjectState(project_id=None)

    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows
        {"_embedded": {"extensions": []}},                      # extensions (empty)
        {"nodes": []},                                          # chart (tool discovery)
        {"items": []},                                          # chart/nodes/aiagents
        {"items": []},                                          # endpoints
    ]
    handlers = make_handlers(mock_client, unscoped, cache)
    result = handlers["sync_remote_state"]({"project_id": "proj-new"})
    data = json.loads(result[0].text)

    assert data["synced"] is True
    assert unscoped.project_id == "proj-new"
    assert unscoped.get("flows", "Main Flow", "id") == "flow-1"


def test_sync_stores_endpoint_token_from_URLToken_field(mock_client, state, cache):
    """sync_remote_state must read URLToken (PascalCase) from the API response — the real AU1 field name."""
    project_id = state.project_id
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},
        {"_embedded": {"extensions": []}},
        {"nodes": []},
        {"items": []},
        {"items": [{"_id": "ep-1", "name": "REST Endpoint", "URLToken": "real-token-abc", "flowId": "flow-ref-1"}]},
    ]
    handlers = make_handlers(mock_client, state, cache)
    handlers["sync_remote_state"]({"project_id": project_id})
    ep = state.get("endpoints", "REST Endpoint")
    assert ep["urlToken"] == "real-token-abc", f"Expected 'real-token-abc', got '{ep.get('urlToken')}'"
    assert ep["flowReferenceId"] == "flow-ref-1", f"Expected 'flow-ref-1', got '{ep.get('flowReferenceId')}'"


def test_sync_remote_state_builds_extension_map(mock_client, state, cache, monkeypatch):
    """sync_remote_state must fetch installed extensions and store type→name index in state."""
    monkeypatch.setattr("cognigy_mcp.tools.state_tools._write_to_dotenv", lambda *a: None)
    mock_client.get.side_effect = [
        {"items": []},                                                   # GET /v2.0/flows
        {"_embedded": {"extensions": [                                   # GET /v2.0/extensions
            {"name": "my-ext", "_links": {"self": {"href": "https://api/v2.0/extensions/ext-1"}}}
        ]}},
        {"_id": "ext-1", "name": "my-ext",                              # GET /v2.0/extensions/ext-1
         "nodes": [{"type": "myNode"}, {"type": "anotherNode"}]},
        {"items": []},                                                   # GET /v2.0/endpoints
    ]
    handlers = make_handlers(mock_client, state, cache)
    handlers["sync_remote_state"]({"project_id": state.project_id})
    ext_map = state.get("extension_map")
    assert ext_map is not None, "extension_map should be written to state"
    assert ext_map["myNode"] == "my-ext"
    assert ext_map["anotherNode"] == "my-ext"
