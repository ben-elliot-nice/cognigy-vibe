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
    assert "relations" not in data
    assert "Start" in data["hierarchy"] or "start" in data["hierarchy"]

    # format="both" restores legacy behavior
    result_both = handlers["get_flow_chart"]({"flow_id": "flow-1", "format": "both"})
    data_both = json.loads(result_both[0].text)
    assert "hierarchy" in data_both
    assert "relations" in data_both


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


# ---------------------------------------------------------------------------
# P1 — Say node config normalisation
# ---------------------------------------------------------------------------

def test_say_node_text_normalised(mock_client, state, cache):
    """config.text string should be lifted into config.say.text array."""
    mock_client.post.return_value = {"_id": "say-1", "type": "say", "label": "Welcome"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "say", "mode": "append", "target": "start", "label": "Welcome",
                 "config": {"text": "Hello world"}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert "say" in call_body["config"]
    assert call_body["config"]["say"]["text"] == ["Hello world"]
    assert "text" not in call_body["config"]


def test_say_node_text_array_normalised(mock_client, state, cache):
    """config.text list should become config.say.text array."""
    mock_client.post.return_value = {"_id": "say-1", "type": "say"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node", "flow_id": "flow-1",
        "body": {"type": "say", "mode": "append", "target": "start",
                 "config": {"text": ["Hello", "Hi there"]}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["config"]["say"]["text"] == ["Hello", "Hi there"]


def test_say_node_existing_envelope_unchanged(mock_client, state, cache):
    """If config.say already present, leave it as-is."""
    mock_client.post.return_value = {"_id": "say-1", "type": "say"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node", "flow_id": "flow-1",
        "body": {"type": "say", "mode": "append", "target": "start",
                 "config": {"say": {"type": "text", "text": ["Already wrapped"]}}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["config"]["say"]["text"] == ["Already wrapped"]


# ---------------------------------------------------------------------------
# P2 — Extension auto-injection
# ---------------------------------------------------------------------------

def test_extension_auto_injected(mock_client, state, cache):
    """setSessionConfig should get @cognigy/voicegateway2 extension automatically."""
    mock_client.post.return_value = {"_id": "ssc-1", "type": "setSessionConfig"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node", "flow_id": "flow-1",
        "body": {"type": "setSessionConfig", "mode": "append", "target": "start",
                 "label": "VG Config", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/voicegateway2"


def test_extension_not_overridden_if_present(mock_client, state, cache):
    """Explicit extension in body should not be overridden."""
    mock_client.post.return_value = {"_id": "ssc-1"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node", "flow_id": "flow-1",
        "body": {"type": "setSessionConfig", "extension": "custom-ext",
                 "mode": "append", "target": "start", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "custom-ext"


def test_aiagentjob_extension_is_basic_nodes(mock_client, state, cache):
    """aiAgentJob must map to @cognigy/basic-nodes, not cognigy-ai-agent."""
    mock_client.post.return_value = {"_id": "job-1", "type": "aiAgentJob"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJob", "mode": "append", "target": "start-id",
                 "label": "My Agent", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/basic-nodes"


def test_aiagentjobtool_extension_is_basic_nodes(mock_client, state, cache):
    """aiAgentJobTool must map to @cognigy/basic-nodes."""
    mock_client.post.return_value = {"_id": "tool-1", "type": "aiAgentJobTool"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJobTool", "mode": "appendChild", "target": "job-1",
                 "label": "My Tool", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/basic-nodes"


def test_aiagenttooltanswer_extension_is_basic_nodes(mock_client, state, cache):
    """aiAgentToolAnswer must map to @cognigy/basic-nodes."""
    mock_client.post.return_value = {"_id": "answer-1", "type": "aiAgentToolAnswer"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentToolAnswer", "mode": "append", "target": "code-1",
                 "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/basic-nodes"


# ---------------------------------------------------------------------------
# P3 — Plural/singular resource_type normalisation
# ---------------------------------------------------------------------------

def test_singular_resource_type_normalised(mock_client, state, cache):
    """'flow' should be normalised to 'flows' for API path construction."""
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flow", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    # API should have been called with /v2.0/flows/flow-1, not /v2.0/flow/flow-1
    call_path = mock_client.get.call_args[0][0]
    assert "/v2.0/flows/" in call_path


def test_get_flow_chart_bare_nodes_no_nodeId(mock_client, state, cache):
    """AU1 bare Start/End nodes: relations have _id but not nodeId — must not raise KeyError."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start-id", "type": "start", "label": "Start"},
            {"_id": "end-id", "type": "end", "label": "End"},
        ],
        "relations": [
            {"_id": "start-id", "nextId": "end-id", "previousId": None, "parentId": None, "childIds": []},
            {"_id": "end-id", "nextId": None, "previousId": "start-id", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-new"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "error" not in data


def test_cognigy_create_knowledge_source_without_id_field(mock_client, state, cache):
    """cognigy_create must not raise KeyError when API response lacks _id.
    Repro: creating a knowledge source returns a response without _id.
    """
    mock_client.post.return_value = {
        "name": "Battery Trade-In Policy",
        "type": "manual",
        "referenceId": "ks-source-ref-123",
        # No "_id" key — this is what the knowledge source API returns
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "knowledgestores/ks123/sources",
        "body": {"name": "Battery Trade-In Policy", "type": "manual"},
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data.get("referenceId") == "ks-source-ref-123"


def test_get_flow_chart_mixed_nodeId_and_id(mock_client, state, cache):
    """Some relations have nodeId, others only _id — both must be indexed correctly."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "n1", "type": "say", "label": "Hello"},
            {"_id": "n2", "type": "say", "label": "Bye"},
        ],
        "relations": [
            {"nodeId": "n1", "_id": "n1", "nextId": "n2", "previousId": None, "parentId": None, "childIds": []},
            {"_id": "n2", "nextId": None, "previousId": "n1", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "error" not in data
