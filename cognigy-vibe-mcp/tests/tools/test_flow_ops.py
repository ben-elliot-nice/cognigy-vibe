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


def test_cognigy_get_cache_key_parity_singular_plural(mock_client, state, cache):
    """A cache entry written under the normalised 'node' key must be readable back
    via resource_type='nodes' — same regression class as #22 (cache-key mismatch)."""
    cache.set("node", "n1", {"_id": "n1", "type": "say"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "nodes",
        "resource_id": "n1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["_source"] == "cache"
    mock_client.get.assert_not_called()


def test_cognigy_get_plural_nodes_missing_flow_id_returns_error(mock_client, state, cache):
    """resource_type='nodes' without flow_id must return the same guidance error as
    singular 'node', not build a malformed path."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "nodes", "resource_id": "n1"})
    data = json.loads(result[0].text)
    assert "flow_id required" in data["error"]
    mock_client.get.assert_not_called()


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


def test_cognigy_invoke_node_move_is_unsupported(mock_client, state, cache):
    """node/move is not a real API endpoint — issue #237: it 404s against every
    tried resource shape. cognigy_invoke must reject it with guidance toward
    cognigy_update's mode/target mechanism instead of POSTing to a fake path."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "operation": "move",
        "body": {"mode": "append", "target": "node-0"},
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "cognigy_update" in data["error"]
    mock_client.post.assert_not_called()


def test_cognigy_invoke_node_move_plural_resource_type_is_unsupported(mock_client, state, cache):
    """resource_type='nodes' must be rejected the same way as 'node'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "nodes",
        "resource_id": "node-1",
        "operation": "move",
        "body": {"mode": "append", "target": "node-0"},
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "cognigy_update" in data["error"]
    mock_client.post.assert_not_called()


def test_cognigy_invoke_knowledgestore_run_hits_connector_path(mock_client, state, cache):
    """resource_type='knowledgestore' + operation='run' must keep the /connectors/{id}/run
    special-case path — normalising to the plural 'knowledgestores' must not break it."""
    mock_client.post.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_invoke"]({
        "resource_type": "knowledgestore",
        "resource_id": "ks123",
        "operation": "run",
        "body": {"connector_id": "conn-1"},
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/knowledgestores/ks123/connectors/conn-1/run",
        {"connector_id": "conn-1"},
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


# ── Issue #207: discovery pointer + nested-path + return-shape doc fixes ────

def test_all_primitive_descriptions_point_to_explain():
    """Every generic primitive must tell the LLM to call explain() before guessing a body shape."""
    for name in ("cognigy_get", "cognigy_list", "cognigy_create", "cognigy_update", "cognigy_delete", "cognigy_invoke"):
        tool = next(t for t in TOOLS if t.name == name)
        assert "explain()" in tool.description, \
            f"{name} description must point to explain() as the discovery mechanism"


def test_cognigy_list_documents_nested_subresource_paths():
    """cognigy_list description must document nested resource_type paths like 'knowledgestores/{id}/connectors'."""
    tool = next(t for t in TOOLS if t.name == "cognigy_list")
    assert "knowledgestores/{id}/connectors" in tool.description or "nested" in tool.description.lower(), \
        "cognigy_list must document that nested sub-resource resource_type paths are supported"


def test_cognigy_update_documents_variable_return_shape():
    """cognigy_update description must warn that the API can return {} on success even with return_full_object=false."""
    tool = next(t for t in TOOLS if t.name == "cognigy_update")
    assert "{}" in tool.description, \
        "cognigy_update must document that the API may return an empty object on some resource_types"
    assert "cognigy_get" in tool.description, \
        "cognigy_update must recommend re-fetching via cognigy_get to confirm a write"


def test_push_code_node_field_descriptions_reference_node_positioning():
    """push_code_node's mode/target Field descriptions must point to node-positioning (regression guard)."""
    from cognigy_mcp.tools.file_push import TOOLS as FILE_PUSH_TOOLS
    tool = next(t for t in FILE_PUSH_TOOLS if t.name == "push_code_node")
    props = tool.inputSchema["properties"]
    assert "node-positioning" in props["mode"]["description"]
    assert "node-positioning" in props["target"]["description"]


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


def test_cognigy_get_fields_all_missing_returns_error(mock_client, state, cache):
    """Regression guard for #238: an entirely-wrong `fields` list must error, not
    silently succeed with a near-empty object."""
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "fields": ["nodes"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on this resource"
    assert data["requested_fields"] == ["nodes"]
    assert "_id" in data["available_fields"]
    assert "name" in data["available_fields"]


def test_cognigy_get_fields_all_missing_excludes_blocked_fields_from_available(mock_client, state, cache):
    """available_fields must reflect the stripped response, not raw internal fields —
    __v shouldn't be advertised as a valid field to request."""
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main", "__v": 3}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "fields": ["nodes"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on this resource"
    assert "__v" not in data["available_fields"]


def test_cognigy_get_fields_only_blocked_field_returns_error_not_near_empty_success(mock_client, state, cache):
    """Regression guard: requesting ONLY a blocked field (e.g. __v) must hit the same
    error path as requesting a genuinely nonexistent field — not match on raw data,
    then get silently emptied by strip_response into a near-empty success."""
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main", "__v": 3}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "fields": ["__v"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on this resource"
    assert data["requested_fields"] == ["__v"]


def test_cognigy_get_cache_hit_fields_all_missing_returns_error(mock_client, state, cache):
    """The fields-all-missing error path must also apply on a cache hit, not just
    the API-fetch branch — cache.get() populates `data` before the fields check runs."""
    cache.set("flows", "flow-1", {"_id": "flow-1", "name": "Main"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "fields": ["nodes"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on this resource"
    mock_client.get.assert_not_called()


def test_cognigy_get_fields_partial_match_still_filters(mock_client, state, cache):
    """At least one valid field must still filter normally, no error."""
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main", "description": "x"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "fields": ["name", "nodes"],
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["name"] == "Main"
    assert "description" not in data


def test_cognigy_list_fields_all_missing_returns_error(mock_client, state, cache):
    """Regression guard for #238: same silent-filter bug in cognigy_list's fields param."""
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1"},
        {"_id": "f2", "name": "Flow 2"},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "fields": ["nodes"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on any item in this list"
    assert data["requested_fields"] == ["nodes"]
    assert "id" in data["available_fields"]
    assert "name" in data["available_fields"]


def test_cognigy_list_fields_partial_match_still_filters(mock_client, state, cache):
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1"},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "fields": ["name", "nodes"],
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["items"][0] == {"name": "Flow 1"}


def test_cognigy_list_full_objects_fields_all_missing_returns_error(mock_client, state, cache):
    """full_objects=True holds raw API items (keyed _id, not id) — the fields-all-missing
    error path must operate on that raw shape, not the simplified {id, name} projection."""
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "createdAt": "2026-01-01"},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "full_objects": True,
        "fields": ["nonexistent"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on any item in this list"
    assert "_id" in data["available_fields"]
    assert "createdAt" in data["available_fields"]


def test_cognigy_list_full_objects_fields_all_missing_excludes_blocked_fields(mock_client, state, cache):
    """available_fields for the full_objects list path must also reflect stripped
    items — __v shouldn't be advertised as a valid field to request."""
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "__v": 2},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "full_objects": True,
        "fields": ["nonexistent"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on any item in this list"
    assert "__v" not in data["available_fields"]


def test_cognigy_list_full_objects_only_blocked_field_returns_error_not_near_empty_success(mock_client, state, cache):
    """Regression guard: requesting ONLY a blocked field across full_objects items must
    hit the error path, not silently produce a nonzero-count list of empty dicts."""
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "__v": 2},
        {"_id": "f2", "name": "Flow 2", "__v": 3},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "full_objects": True,
        "fields": ["__v"],
    })
    data = json.loads(result[0].text)
    assert data["error"] == "none of the requested fields exist on any item in this list"
    assert data["requested_fields"] == ["__v"]


def test_cognigy_list_full_objects_fields_partial_match_still_filters(mock_client, state, cache):
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "createdAt": "2026-01-01"},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "full_objects": True,
        "fields": ["createdAt", "nonexistent"],
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["items"][0] == {"createdAt": "2026-01-01"}


def test_cognigy_list_fields_matches_at_least_one_item_not_all(mock_client, state, cache):
    """available_fields is a union across items — a field present on only ONE of several
    heterogeneous items must still count as matched, not require presence on every item."""
    mock_client.get.return_value = {"items": [
        {"_id": "f1", "name": "Flow 1", "description": "has a description"},
        {"_id": "f2", "name": "Flow 2"},
    ]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "fields": ["description"],
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["items"] == [{"description": "has a description"}, {}]


def test_cognigy_list_fields_with_empty_items_does_not_error(mock_client, state, cache):
    """An empty result list has nothing to validate `fields` against — must not error
    just because there's nothing to match."""
    mock_client.get.return_value = {"items": []}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({
        "resource_type": "flows",
        "fields": ["nonexistent"],
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data["items"] == []
    assert data["count"] == 0


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


def test_cognigy_get_propagates_api_error_as_structured_response(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.get.side_effect = ApiError(400, "Invalid value for field 'sourceType'")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 400
    assert "Invalid value for field 'sourceType'" in data["detail"]


def test_cognigy_list_propagates_api_error_as_structured_response(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.get.side_effect = ApiError(403, "Forbidden")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "flows", "project_id": "proj-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 403
    assert "Forbidden" in data["detail"]


def test_cognigy_create_propagates_api_error_as_structured_response(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.post.side_effect = ApiError(400, "Invalid value for field 'sourceType'")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({"resource_type": "knowledgestores", "body": {"sourceType": "bogus"}})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 400
    assert "sourceType" in data["detail"]


def test_cognigy_update_get_current_propagates_api_error(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.get.side_effect = ApiError(404, "Not found")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_update"]({
        "resource_type": "flows", "resource_id": "flow-1", "body": {"name": "New Name"},
    })
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 404
    assert "Not found" in data["detail"]


def test_cognigy_update_patch_propagates_api_error(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.get.return_value = {"_id": "flow-1", "type": "flow"}
    mock_client.patch.side_effect = ApiError(500, "Encountered an unknown error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_update"]({
        "resource_type": "flows", "resource_id": "flow-1", "body": {"name": "New Name"},
    })
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 500
    assert "Encountered an unknown error" in data["detail"]


def test_cognigy_delete_propagates_api_error(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.delete.side_effect = ApiError(400, "Cannot delete: in use")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_delete"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 400
    assert "Cannot delete: in use" in data["detail"]


def test_cognigy_invoke_propagates_api_error_as_structured_response(mock_client, state, cache):
    """Regression test for #216: cognigy_invoke must surface the upstream status/detail
    instead of letting ApiError propagate into an opaque unstructured MCP error."""
    from cognigy_mcp.api import ApiError
    mock_client.post.side_effect = ApiError(400, "Invalid value for field 'sourceType'")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "knowledgestore",
        "resource_id": "ks123",
        "operation": "run",
        "body": {"connector_id": "conn-1", "sourceType": "bogus"},
    })
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 400
    assert "sourceType" in data["detail"]


def test_get_flow_chart_propagates_api_error_as_structured_response(mock_client, state, cache):
    from cognigy_mcp.api import ApiError
    mock_client.get.side_effect = ApiError(404, "Flow not found")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 404
    assert "Flow not found" in data["detail"]


def test_cognigy_invoke_propagates_retriable_api_error_as_structured_response(mock_client, state, cache):
    """RetriableApiError is a subclass of ApiError — confirm it's caught by the same
    except ApiError block rather than falling through to the generic exception handler."""
    from cognigy_mcp.api import RetriableApiError
    mock_client.post.side_effect = RetriableApiError(503, "Service Unavailable")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "aiagent",
        "resource_id": "agent-1",
        "operation": "train",
    })
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 503
    assert "Service Unavailable" in data["detail"]


def test_cognigy_invoke_propagates_unexpected_non_api_error_as_structured_response(mock_client, state, cache):
    """Network/decode failures (e.g. httpx timeouts, malformed JSON) are not ApiError —
    they must still be caught and surfaced as structured errors, not left to propagate
    into the MCP SDK's opaque unstructured error (the original #216 symptom)."""
    mock_client.post.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_invoke"]({
        "resource_type": "aiagent",
        "resource_id": "agent-1",
        "operation": "train",
    })
    data = json.loads(result[0].text)
    assert data["error"] == "unexpected_error"
    assert "Expecting value" in data["detail"]
