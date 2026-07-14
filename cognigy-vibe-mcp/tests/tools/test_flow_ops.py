import json
import pytest
from unittest.mock import MagicMock, patch
from cognigy_mcp.tools.flow_ops import make_handlers, TOOLS, _normalise_say_config


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


def test_cognigy_get_aiagents_calls_canonical_endpoint(mock_client, state, cache):
    """cognigy_get for aiagents must call /v2.0/aiagents/{id}, not a chart/node endpoint.

    Regression guard for issue #22: cache pollution caused cognigy_get to return
    chart-node data. On cache miss the live call must go to the canonical path.
    """
    canonical_resource = {
        "_id": "agent-1",
        "name": "My Agent",
        "speakingStyle": "formal",
        "knowledgeReferenceId": "ks-xyz",
    }
    mock_client.get.return_value = canonical_resource
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "aiagents", "resource_id": "agent-1"})
    data = json.loads(result[0].text)

    called_path = mock_client.get.call_args[0][0]
    assert called_path == "/v2.0/aiagents/agent-1", (
        f"Expected /v2.0/aiagents/agent-1, got {called_path}"
    )
    assert data.get("speakingStyle") == "formal"
    assert "_source" in data


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


def test_cognigy_get_plural_nodes_uses_chart_path(mock_client, state, cache):
    """Regression guard for issue #213: resource_type='nodes' (plural) must route
    to the chart-nested path, same as singular 'node', instead of falling through
    to the nonexistent /v2.0/nodes/{id} endpoint."""
    mock_client.get.return_value = {"_id": "node-1", "type": "say"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "nodes",
        "resource_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    mock_client.get.assert_called_once_with("/v2.0/flows/flow-1/chart/nodes/node-1")
    assert data["_id"] == "node-1"


def test_cognigy_update_plural_nodes_uses_chart_path(mock_client, state, cache):
    mock_client.get.return_value = {"_id": "node-1", "type": "say"}
    mock_client.patch.return_value = {"_id": "node-1", "type": "say"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_update"]({
        "resource_type": "nodes",
        "resource_id": "node-1",
        "flow_id": "flow-1",
        "body": {"label": "Updated"},
    })
    assert mock_client.get.call_args[0][0] == "/v2.0/flows/flow-1/chart/nodes/node-1"
    assert mock_client.patch.call_args[0][0] == "/v2.0/flows/flow-1/chart/nodes/node-1"


def test_cognigy_delete_plural_nodes_uses_chart_path(mock_client, state, cache):
    mock_client.delete.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_delete"]({
        "resource_type": "nodes",
        "resource_id": "node-1",
        "flow_id": "flow-1",
    })
    mock_client.delete.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1"
    )


def test_cognigy_create_plural_nodes_routes_to_chart(mock_client, state, cache):
    mock_client.post.return_value = {"_id": "node-1", "type": "say"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "nodes",
        "flow_id": "flow-1",
        "body": {"type": "say"},
    })
    assert mock_client.post.call_args[0][0] == "/v2.0/flows/flow-1/chart/nodes"


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


def test_cognigy_invoke_move_node_plural_resource_type(mock_client, state, cache):
    """resource_type='nodes' must route the same as 'node' — invoke should normalise like get/list/create/update/delete."""
    mock_client.post.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_invoke"]({
        "resource_type": "nodes",
        "resource_id": "node-1",
        "operation": "move",
        "body": {"mode": "append", "target": "node-0"},
        "flow_id": "flow-1",
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1/move",
        {"mode": "append", "target": "node-0"},
    )


def test_get_flow_chart_hierarchy_uses_real_api_format(mock_client, state, cache):
    """_build_hierarchy must use rel['node'], rel['next'], rel['children'] — not nodeId/nextId/childIds."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start-id", "type": "start", "label": "Start"},
            {"_id": "say-id",   "type": "say",   "label": "Hello"},
        ],
        "relations": [
            {"node": "start-id", "next": "say-id", "children": [], "_id": "rel-start"},
            {"node": "say-id",   "next": None,      "children": [], "_id": "rel-say"},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    hierarchy = data["hierarchy"]
    assert "[start] Start (start-id)" in hierarchy
    assert "[say] Hello (say-id)" in hierarchy
    assert "relations" not in data


def test_get_flow_chart_cycle_marker(mock_client, state, cache):
    """Cyclic next references must produce [CYCLE] marker, not RecursionError."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "a", "type": "say", "label": "A"},
            {"_id": "b", "type": "say", "label": "B"},
        ],
        "relations": [
            {"node": "a", "next": "b", "children": [], "_id": "rel-a"},
            {"node": "b", "next": "a", "children": [], "_id": "rel-b"},  # cycle
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


def test_aiagenttooltanswer_answer_injected_when_missing(mock_client, state, cache):
    """Empty config:{} must get the canonical answer field injected."""
    mock_client.post.return_value = {"_id": "answer-1", "type": "aiAgentToolAnswer"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentToolAnswer", "mode": "append", "target": "code-1",
                 "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["config"]["answer"] == "{{JSON.stringify(context.toolResponse)}}"
    assert call_body["config"]["maxLoops"] == 4


def test_aiagenttooltanswer_existing_answer_unchanged(mock_client, state, cache):
    """If answer is already set, normalization must leave it unchanged."""
    mock_client.post.return_value = {"_id": "answer-1", "type": "aiAgentToolAnswer"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentToolAnswer", "mode": "append", "target": "code-1",
                 "config": {"answer": "{{JSON.stringify(context.toolResponse)}}", "maxLoops": 8}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["config"]["answer"] == "{{JSON.stringify(context.toolResponse)}}"
    assert call_body["config"]["maxLoops"] == 8


def test_aiagenttooltanswer_no_config_key_unchanged(mock_client, state, cache):
    """If no config key at all, normalization must not add one (body sent as-is)."""
    mock_client.post.return_value = {"_id": "answer-1", "type": "aiAgentToolAnswer"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentToolAnswer", "mode": "append", "target": "code-1"},
    })
    call_body = mock_client.post.call_args[0][1]
    assert "config" not in call_body


def test_inject_extension_uses_dynamic_map_as_fallback(mock_client, state, cache):
    """A node type unknown to the static map should get its extension from state['extension_map']."""
    state.set("extension_map", value={"myCustomNode": "my-custom-ext"})
    mock_client.post.return_value = {"_id": "node-1", "type": "myCustomNode", "label": "My Node"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {
            "type": "myCustomNode",
            "mode": "append",
            "target": "start-id",
            "label": "My Node",
            "config": {},
        },
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "my-custom-ext"


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


def test_get_flow_chart_hierarchy_is_structured(mock_client, state, cache):
    """Child nodes must be indented under their parent, not listed as separate roots."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "job-id",  "type": "aiAgentJob",    "label": "Concierge"},
            {"_id": "tool-id", "type": "aiAgentJobTool", "label": "authenticate"},
        ],
        "relations": [
            {"node": "job-id",  "next": None, "children": ["tool-id"], "_id": "rel-job"},
            {"node": "tool-id", "next": None, "children": [],          "_id": "rel-tool"},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    hierarchy = json.loads(result[0].text)["hierarchy"]
    lines = hierarchy.splitlines()
    job_line  = next(l for l in lines if "Concierge" in l)
    tool_line = next(l for l in lines if "authenticate" in l)
    # tool must be indented more than job
    assert len(tool_line) - len(tool_line.lstrip()) > len(job_line) - len(job_line.lstrip())
    # only one root — job node
    assert sum(1 for l in lines if not l.startswith("  ")) == 1


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


def test_cognigy_create_node_saved_to_nodes_state_key(mock_client, state, cache):
    """Created nodes must be stored under 'nodes' key so resolve_resource('nodes', ...) finds them."""
    mock_client.post.return_value = {"_id": "node-xyz", "type": "say", "label": "Greeting"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "say", "mode": "append", "target": "start-id", "label": "Greeting",
                 "config": {"say": {"type": "text", "text": ["Hello"]}}},
    })
    entry = state.get("nodes", "Greeting")
    assert entry is not None, "Node not found in state under 'nodes' key"
    assert entry["id"] == "node-xyz"
    assert entry["flowId"] == "flow-1"


def test_get_flow_chart_shows_type_and_label_with_real_api_fields(mock_client, state, cache):
    """Chart using real AU1 field names (node/next/children) must render [type] label — not [] id (id)."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start-1", "type": "start", "label": "Start"},
            {"_id": "say-1", "type": "say", "label": "Hello there"},
        ],
        "relations": [
            {"node": "start-1", "next": "say-1", "children": [], "_id": "rel-a"},
            {"node": "say-1", "next": None, "children": [], "_id": "rel-b"},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "[start] Start" in data["hierarchy"], f"Expected '[start] Start' in: {data['hierarchy']}"
    assert "[say] Hello there" in data["hierarchy"], f"Expected '[say] Hello there' in: {data['hierarchy']}"


def test_cognigy_list_handles_bare_list_response(mock_client, state, cache):
    """Endpoints that return a bare list (e.g. /v2.0/aiagents/{id}/jobs) must not crash."""
    mock_client.get.return_value = [
        {"_id": "job-1", "type": "aiAgentJob", "name": "Job One"},
        {"_id": "job-2", "type": "aiAgentJob", "name": "Job Two"},
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "jobs", "agent_id": "agent-abc"})
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["count"] == 2
    assert data["items"][0]["id"] == "job-1"
    assert data["items"][1]["id"] == "job-2"


def test_get_flow_chart_format_both_includes_raw(mock_client, state, cache):
    """format='both' must include hierarchy, nodes, and relations."""
    mock_client.get.return_value = {
        "nodes": [{"_id": "n1", "type": "start", "label": "Start"}],
        "relations": [{"node": "n1", "next": None, "children": [], "_id": "rel-1"}],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1", "format": "both"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "nodes" in data
    assert "relations" in data


def test_cognigy_list_node_returns_helpful_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for rtype in ("node", "nodes"):
        result = handlers["cognigy_list"]({"resource_type": rtype})
        data = json.loads(result[0].text)
        assert "error" in data
        assert "get_flow_chart" in data["error"]
        mock_client.get.assert_not_called()


def test_cognigy_create_snapshot_posts_to_correct_url(mock_client, state, cache):
    mock_client.post.return_value = {
        "_id": "job-abc123",
        "status": "queued",
        "type": "createSnapshot",
        "parameters": {"properties": {"name": "My Snapshot", "description": "test"}},
        "progress": 0,
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "snapshot",
        "body": {"name": "My Snapshot", "description": "test", "projectId": "proj-1"},
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/snapshots",
        {"name": "My Snapshot", "description": "test", "projectId": "proj-1"},
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "queued" or data.get("type") == "createSnapshot"


# ── Issue #37: cognigy_create description misleads on branch insertion ──

def test_cognigy_create_description_documents_branch_marker_pattern():
    """cognigy_create description must tell users to append on branch marker for Once/IF branches."""
    tool = next(t for t in TOOLS if t.name == "cognigy_create")
    assert "branch marker" in tool.description, \
        "cognigy_create description must mention 'branch marker' pattern for Once/IF branch insertion"


def test_cognigy_create_aiagentjobtool_blocked(mock_client, state, cache):
    """cognigy_create must redirect aiAgentJobTool to push_agent_tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJobTool", "mode": "appendChild", "target": "job-1", "config": {}},
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "push_agent_tool" in data["error"]
    mock_client.post.assert_not_called()


def test_say_normalise_does_not_inject_temperature():
    """Say node defaults must not include generativeAI_temperature.
    Temperature belongs on the AI Agent Job Node, not Say nodes."""
    result = _normalise_say_config({"text": "Hello world"})
    assert "generativeAI_temperature" not in result


# ---------------------------------------------------------------------------
# Response filtering — strip_response applied at full-object return paths
# ---------------------------------------------------------------------------

def test_cognigy_get_strips_internal_fields(mock_client, state, cache):
    mock_client.get.return_value = {
        "_id": "node-1",
        "__v": 42,
        "config": {"code": "input.text", "transpiled": "a" * 1000},
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "__v" not in data
    assert "transpiled" not in data["config"]
    assert data["config"]["code"] == "input.text"


def test_cognigy_list_full_objects_strips_each_item(mock_client, state, cache):
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "__v": 1},
        {"_id": "f2", "name": "Flow 2", "__v": 2},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "flows", "full_objects": True})
    data = json.loads(result[0].text)
    for item in data["items"]:
        assert "__v" not in item
    assert data["items"][0]["_id"] == "f1"


def test_cognigy_list_simplified_not_affected_by_filter(mock_client, state, cache):
    """Default (simplified) list must not be touched by the filter — it already projects to {id, name}."""
    mock_client.get.return_value = {"items": [{"_id": "f1", "name": "Flow 1", "__v": 1}]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "flows"})
    data = json.loads(result[0].text)
    # Simplified path only emits id/name — __v was never included; just assert no crash
    assert data["items"][0]["id"] == "f1"


def test_cognigy_create_return_full_object_strips_internal_fields(mock_client, state, cache):
    mock_client.post.return_value = {
        "_id": "f1",
        "name": "Flow 1",
        "__v": 3,
        "config": {"transpiled": "big compiled output"},
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "flows",
        "body": {"name": "Flow 1"},
        "return_full_object": True,
    })
    data = json.loads(result[0].text)
    assert "__v" not in data
    assert "transpiled" not in data.get("config", {})
    assert data["name"] == "Flow 1"


def test_cognigy_update_return_full_object_strips_internal_fields(mock_client, state, cache):
    mock_client.get.return_value = {"_id": "f1", "name": "Flow 1"}
    mock_client.patch.return_value = {"_id": "f1", "name": "Flow 1 updated", "__v": 4}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_update"]({
        "resource_type": "flows",
        "resource_id": "f1",
        "body": {"name": "Flow 1 updated"},
        "return_full_object": True,
    })
    data = json.loads(result[0].text)
    assert "__v" not in data
    assert data["name"] == "Flow 1 updated"


def test_get_flow_chart_raw_strips_node_internal_fields(mock_client, state, cache):
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "n1", "type": "code", "__v": 1, "config": {"code": "input.text", "transpiled": "big"}},
        ],
        "relations": [],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1", "format": "raw"})
    data = json.loads(result[0].text)
    node = data["nodes"][0]
    assert "__v" not in node
    assert "transpiled" not in node["config"]
    assert node["config"]["code"] == "input.text"


def test_get_flow_chart_both_strips_node_internal_fields(mock_client, state, cache):
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "n1", "type": "code", "__v": 2, "config": {"code": "input.text", "transpiled": "big"}},
        ],
        "relations": [{"node": "n1", "next": None, "children": [], "_id": "rel-1"}],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1", "format": "both"})
    data = json.loads(result[0].text)
    node = data["nodes"][0]
    assert "__v" not in node
    assert "transpiled" not in node["config"]


def test_cognigy_update_merge_config_strips_blocked_fields_before_patch(mock_client, state, cache):
    """merge_config must not re-upload config.transpiled to the API."""
    mock_client.get.return_value = {
        "_id": "node-1",
        "config": {"code": "input.text", "transpiled": "compiled...", "otherKey": "keep"},
    }
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "input.text", "otherKey": "keep"}}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_update"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "flow_id": "flow-1",
        "body": {"config": {}},
        "merge_config": True,
    })
    call_body = mock_client.patch.call_args[0][1]
    assert "transpiled" not in call_body["config"]
    assert call_body["config"]["code"] == "input.text"
    assert call_body["config"]["otherKey"] == "keep"


def test_get_flow_chart_hierarchy_strips_node_internal_fields(mock_client, state, cache):
    """hierarchy format (the default) must strip __v and config.transpiled from nodes."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "n1", "type": "code", "__v": 5, "config": {"code": "input.text", "transpiled": "big"}, "label": "My Code"},
        ],
        "relations": [{"node": "n1", "next": None, "children": [], "_id": "rel-1"}],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    # hierarchy string should still render correctly
    assert "[code] My Code" in data["hierarchy"]
    # raw nodes must not be in the hierarchy response, but the hierarchy itself should be clean
    assert "__v" not in data


def test_cognigy_invoke_strips_internal_fields(mock_client, state, cache):
    mock_client.post.return_value = {"_id": "flow-2", "__v": 1, "name": "Cloned Flow"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "flow",
        "resource_id": "flow-1",
        "operation": "clone",
        "body": {},
    })
    data = json.loads(result[0].text)
    assert "__v" not in data
    assert data["name"] == "Cloned Flow"


def test_cognigy_get_missing_required_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "resource_type" for d in data["details"])


def test_cognigy_get_fields_wrong_type_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "id-1",
        "fields": "not-a-list",
    })
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "fields" for d in data["details"])


def test_cognigy_list_missing_required_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "resource_type" for d in data["details"])


def test_cognigy_create_missing_body_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({"resource_type": "flows"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "body" for d in data["details"])
