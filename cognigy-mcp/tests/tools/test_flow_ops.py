import json
import pytest
from unittest.mock import MagicMock, patch
from cognigy_mcp.tools.flow_ops import make_handlers, TOOLS


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    for expected in [
        "cognigy_get", "cognigy_list", "cognigy_create",
        "cognigy_update", "cognigy_delete", "cognigy_invoke", "get_flow_chart",
    ]:
        assert expected in names


def test_cognigy_get_cache_hit(mock_client, state, cache):
    cache.set("flows", "flow-1", {"_id": "flow-1", "name": "Main"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["_id"] == "flow-1"
    assert data["_source"] == "cache"
    mock_client.get.assert_not_called()


def test_cognigy_get_cache_miss_calls_api(mock_client, state, cache):
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["_source"] == "api"
    mock_client.get.assert_called_once()


def test_cognigy_list_returns_items(mock_client, state, cache):
    mock_client.get.return_value = {"items": [{"_id": "f1", "name": "Flow 1"}]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "flows", "project_id": "proj-1"})
    data = json.loads(result[0].text)
    assert len(data["items"]) == 1


def test_cognigy_create_saves_to_state(mock_client, state, cache):
    mock_client.post.return_value = {"_id": "new-flow", "name": "My Flow"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "flows",
        "body": {"name": "My Flow", "projectId": "proj-1"},
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "new-flow"
    assert state.get("flows", "My Flow", "id") == "new-flow"


def test_cognigy_update_with_merge_config(mock_client, state, cache):
    cache.set("flows", "flow-1", {"_id": "flow-1", "config": {"a": 1, "b": 2}})
    mock_client.get.return_value = {"_id": "flow-1", "config": {"a": 1, "b": 2}}
    mock_client.patch.return_value = {"_id": "flow-1", "config": {"a": 1, "b": 99}}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_update"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "body": {"config": {"b": 99}},
        "merge_config": True,
    })
    call_body = mock_client.patch.call_args[0][1]
    assert call_body["config"]["a"] == 1
    assert call_body["config"]["b"] == 99


def test_cognigy_delete_node_uses_chart_path(mock_client, state, cache):
    mock_client.delete.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_delete"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "flow_id": "flow-1",
    })
    mock_client.delete.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1"
    )


def test_cognigy_delete_regular_resource(mock_client, state, cache):
    mock_client.delete.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_delete"]({"resource_type": "flows", "resource_id": "flow-1"})
    mock_client.delete.assert_called_once_with("/v2.0/flows/flow-1")


def test_cognigy_invoke_move_node(mock_client, state, cache):
    mock_client.post.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_invoke"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "operation": "move",
        "body": {"mode": "append", "target": "node-0"},
        "flow_id": "flow-1",
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1/move",
        {"mode": "append", "target": "node-0"},
    )


def test_get_flow_chart_returns_hierarchy(mock_client, state, cache):
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start", "type": "start", "label": "Start", "config": {}},
            {"_id": "say-1", "type": "say", "label": "Hello", "config": {}},
        ],
        "relations": [
            {"nodeId": "start", "nextId": "say-1", "previousId": None, "parentId": None, "childIds": []},
            {"nodeId": "say-1", "nextId": None, "previousId": "start", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "relations" in data
    assert "Start" in data["hierarchy"] or "start" in data["hierarchy"]


def test_build_hierarchy_no_cycle_crash(mock_client, state, cache):
    """Cyclic nextId should produce [CYCLE] marker, not RecursionError."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "a", "type": "say", "label": "A", "config": {}},
            {"_id": "b", "type": "say", "label": "B", "config": {}},
        ],
        "relations": [
            {"nodeId": "a", "nextId": "b", "previousId": None, "parentId": None, "childIds": []},
            {"nodeId": "b", "nextId": "a", "previousId": "a", "parentId": None, "childIds": []},  # cycle
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "CYCLE" in data["hierarchy"]


def test_cognigy_create_node_missing_flow_id_returns_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({"resource_type": "node", "body": {"type": "say"}})
    data = json.loads(result[0].text)
    assert "error" in data


def test_cognigy_update_merge_config_is_deep(mock_client, state, cache):
    """Deep merge should preserve nested keys not in the update body."""
    mock_client.get.return_value = {
        "_id": "node-1",
        "config": {"outer": {"a": 1, "b": 2}, "other": "keep"}
    }
    mock_client.patch.return_value = {"_id": "node-1", "config": {"outer": {"a": 1, "b": 99}, "other": "keep"}}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_update"]({
        "resource_type": "flows",
        "resource_id": "node-1",
        "body": {"config": {"outer": {"b": 99}}},
        "merge_config": True,
    })
    call_body = mock_client.patch.call_args[0][1]
    assert call_body["config"]["outer"]["a"] == 1   # preserved by deep merge
    assert call_body["config"]["outer"]["b"] == 99  # updated
    assert call_body["config"]["other"] == "keep"   # preserved by deep merge
