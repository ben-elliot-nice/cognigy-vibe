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
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},   # list flows
        {"nodes": []},  # chart for Main Flow (tool discovery)
        {"items": [{"_id": "agent-1", "name": "My Agent"}]},   # list agents
        {"items": [{"_id": "ep-1", "name": "REST", "urlToken": "tok123", "flowReferenceId": "flow-1"}]},  # list endpoints
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data.get("synced") is True
    assert state.get("flows", "Main Flow", "id") == "flow-1"


def test_sync_handles_list_failure_gracefully(mock_client, state, cache):
    """sync_remote_state should return synced=True even if agents/endpoints fail."""
    project_id = state.project_id
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows OK
        {"nodes": []},                                          # chart OK
        Exception("API unavailable"),                          # agents FAIL
        Exception("API unavailable"),                          # endpoints FAIL
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data["synced"] is True
    assert "errors" in data
    assert any("agents" in e for e in data["errors"])
    # Flows should still be registered despite other failures
    assert state.get("flows", "Main Flow", "id") == "flow-1"


def test_cognigy_list_singular_resource_type_normalised(mock_client, state, cache):
    """'project' should be normalised to 'projects' in the API path."""
    mock_client.get.return_value = {"items": [{"_id": "p1", "name": "My Project"}]}
    handlers = flow_make_handlers(mock_client, state, cache)
    handlers["cognigy_list"]({"resource_type": "project", "project_id": "proj-1"})
    call_path = mock_client.get.call_args[0][0]
    assert "projects" in call_path
    assert "project?" not in call_path  # was bug: literal None in query


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
