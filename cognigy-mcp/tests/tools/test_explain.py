# tests/tools/test_explain.py
import json
import pytest
from cognigy_mcp.tools.explain import make_handlers, TOOLS, TOPICS


def test_tool_exported():
    assert any(t.name == "explain" for t in TOOLS)


def test_tool_description_contains_all_topic_names():
    tool = next(t for t in TOOLS if t.name == "explain")
    for topic in TOPICS:
        assert topic in tool.description, f"Topic '{topic}' missing from explain description"


def test_explain_no_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({})
    text = result[0].text
    assert "Topics" in text
    for topic in TOPICS:
        assert topic in text


def test_explain_known_topic_returns_content(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for topic in TOPICS:
        result = handlers["explain"]({"topic": topic})
        text = result[0].text
        assert len(text) > 100, f"Topic '{topic}' returned too-short content: {text!r}"


def test_explain_unknown_topic_returns_topic_list(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "nonexistent-topic"})
    text = result[0].text
    assert "nonexistent-topic" in text
    assert "Topics" in text


def test_explain_knowledge_store_has_correct_source_creation_fields(mock_client, state, cache):
    """Regression: knowledge-store topic must not document invalid API fields in examples."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "knowledge-store"})
    text = result[0].text

    # Must document the correct type value in an example
    assert '"manual"' in text, "Should document type: 'manual'"

    # Must document chunks endpoint
    assert "chunks" in text, "Should document adding content as chunks"

    # Must NOT document knowledgeStoreId as part of a valid body example
    assert 'body={"knowledgeStoreId"' not in text, "knowledgeStoreId must not be in body examples"


# ── Issue #14: IF node type string and creation docs ────────────────────────

def test_flow_chart_reading_if_node_type_is_if_not_ifthenelse(mock_client, state, cache):
    """flow-chart-reading must document type string as 'if', not 'ifThenElse'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert 'ifThenElse (note: NOT "if")' not in text, \
        "Must not document inverted type string"
    assert 'if (note: NOT "ifThenElse")' in text, \
        "Must document correct type string: if (note: NOT \"ifThenElse\")"


def test_flow_chart_reading_if_node_is_createable_via_api(mock_client, state, cache):
    """flow-chart-reading must document that IF nodes CAN be created via cognigy_create."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert "Cannot be created via cognigy_create" not in text, \
        "Must not claim IF nodes are UI-only"
    assert 'cognigy_create' in text and '"type": "if"' in text, \
        "Must document cognigy_create with type 'if'"


def test_flow_chart_reading_if_node_config_schema(mock_client, state, cache):
    """flow-chart-reading must document the correct condition config schema."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert '"condition"' in text, "Must document top-level 'condition' key"
    assert "conditions[0]" not in text, "Must not document wrong schema 'conditions[0]'"


def test_node_types_if_type_string(mock_client, state, cache):
    """node-types must document type string 'if', not 'ifThenElse'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "ifThenElse        Conditional (NOT" not in text, \
        "node-types must not have inverted ifThenElse entry"
    assert "if                Conditional (NOT" in text, \
        "node-types must have correct 'if' entry"
    assert "create in UI only" not in text, \
        "node-types must not say 'create in UI only' for if nodes"


def test_extension_map_if_type_string(mock_client, state, cache):
    """extension-map must list 'if' not 'ifThenElse' for the conditional node type."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "extension-map"})
    text = result[0].text
    assert "ifThenElse          Conditional branch (create in UI" not in text, \
        "extension-map must not have UI-only ifThenElse entry"
    assert "if                  Conditional branch" in text, \
        "extension-map must have 'if' conditional branch entry"


# ── Issue #21: xApp extension strings ───────────────────────────────────────

def test_extension_map_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """extension-map must document xApp nodes as @cognigy/basic-nodes, not cxone-utils."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "extension-map"})
    text = result[0].text
    assert '### xApp nodes (extension: "cxone-utils")' not in text, \
        "extension-map must not document xApp extension as cxone-utils"
    assert '### xApp nodes (extension: "@cognigy/basic-nodes")' in text, \
        "extension-map must document xApp extension as @cognigy/basic-nodes"


def test_node_wiring_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """node-wiring inline examples must use @cognigy/basic-nodes for xApp nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-wiring"})
    text = result[0].text
    assert '"extension": "cxone-utils"' not in text, \
        "node-wiring must not document cxone-utils extension"
    assert '"initAppSession"' in text and '"@cognigy/basic-nodes"' in text, \
        "node-wiring must document initAppSession with @cognigy/basic-nodes"


def test_xapp_delivery_extension_is_basic_nodes(mock_client, state, cache):
    """xapp-delivery must document setHTMLAppState with @cognigy/basic-nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-delivery"})
    text = result[0].text
    assert 'extension: "cxone-utils"' not in text, \
        "xapp-delivery must not reference cxone-utils extension"
    assert 'extension: "@cognigy/basic-nodes"' in text, \
        "xapp-delivery must document @cognigy/basic-nodes for setHTMLAppState"


def test_node_types_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """node-types must document xApp nodes as @cognigy/basic-nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "cxone-utils" not in text, \
        "node-types must not reference cxone-utils"
    assert "initAppSession" in text and "@cognigy/basic-nodes" in text, \
        "node-types must reference @cognigy/basic-nodes for xApp nodes"


# ── Issue #15 (doc): xapp-event-handling Variant B inject path ──────────────

def test_xapp_event_handling_variant_b_inject_path(mock_client, state, cache):
    """xapp-event-handling must not document the non-existent management API inject path."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "POST /v2.0/projects/{projectId}/sessions/{sessionId}" not in text, \
        "Must not document the non-existent management API path (returns 404 on AU1)"
    assert "cognigy-endpoint-" in text or "urlToken" in text, \
        "Must document the correct REST endpoint injection path"


# ── Associated: node-wiring relation field names ─────────────────────────────

def test_node_wiring_relation_field_names_are_correct(mock_client, state, cache):
    """node-wiring must document actual API field names: 'node', 'next', 'children'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-wiring"})
    text = result[0].text
    assert '"nodeId"' not in text, \
        "node-wiring must not document 'nodeId' — actual field is 'node'"
    assert '"nextId"' not in text, \
        "node-wiring must not document 'nextId' — actual field is 'next'"
    assert '"childIds"' not in text, \
        "node-wiring must not document 'childIds' — actual field is 'children'"
    assert '"node"' in text, "node-wiring must document 'node' field"
    assert '"next"' in text, "node-wiring must document 'next' field"
    assert '"children"' in text, "node-wiring must document 'children' field"


def test_node_positioning_documents_insert_before_workaround(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "insertBefore" in text, "Should mention insertBefore by name"
    assert "predecessor" in text, "Should document the predecessor-node workaround"
    assert "move" in text.lower(), "Should mention the move operation as alternative"


def test_node_positioning_documents_if_branch_population(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "IF node" in text or "if node" in text.lower(), "Should document IF node branch pattern"
    assert "Then" in text and "Else" in text, "Should name both branch containers"
    assert "childIds[0]" in text or "children[0]" in text, "Should document how to find branch marker IDs"
    assert '"append"' in text, "Should document append (not appendChild) as the correct mode for branch content"


def test_node_positioning_branch_content_uses_append_sibling(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "sibling" in text.lower(), "Should explain append creates a sibling of the branch marker, not a child"
    assert "WRONG" in text, "Should explicitly label appendChild as wrong for branch content insertion"


def test_project_snapshots_topic_exists_and_documents_api(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "project-snapshots"})
    text = result[0].text
    assert len(text) > 100
    assert "snapshot" in text.lower()
    assert "description" in text, "Should document the required description field"
    assert "queued" in text, "Should explain the async/queued response"
    assert "cognigy_create" in text, "Should show how to create via MCP tool"


# ── Issue #31: flow-chart-reading IF branch population contradicts node-positioning ──

def test_flow_chart_reading_if_branch_uses_append_not_appendchild(mock_client, state, cache):
    """flow-chart-reading must document mode='append' for IF branches, not mode='appendChild'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert 'mode="appendChild"' not in text, \
        "flow-chart-reading must not document appendChild for IF branches (contradicts node-positioning)"
    assert 'mode="append"' in text and 'branch-marker' in text, \
        "flow-chart-reading must document mode='append' with branch-marker as target"


# ── Issue #34: say node config schema ───────────────────────────────────────

def test_say_node_topic_exists(mock_client, state, cache):
    """say-node must be a recognised explain topic."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert "Unknown topic" not in text, "say-node must be a known topic"
    assert len(text) > 100


def test_say_node_text_is_string_array(mock_client, state, cache):
    """say-node must document text as a plain string array, not array of objects."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert '"text": ["' in text, \
        'say-node must show text as a plain string array, e.g. "text": ["Hello"]'
    assert '"text": [{"type"' not in text, \
        'say-node must not document text as array of objects'
    assert '"text": [{"content"' not in text, \
        'say-node must not document text as array of objects with content key'


def test_say_node_required_fields_documented(mock_client, state, cache):
    """say-node must document the required _cognigy and _data fields."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert '"_cognigy": {}' in text, "say-node must document _cognigy: {}"
    assert '"_data"' in text, "say-node must document _data field"


def test_say_node_generative_ai_custom_inputs_is_array(mock_client, state, cache):
    """say-node must document generativeAI_customInputs as empty array, not empty string."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert 'generativeAI_customInputs' in text, \
        "say-node must mention generativeAI_customInputs"
    assert '"generativeAI_customInputs": []' in text, \
        "say-node must document generativeAI_customInputs as empty array []"
    assert '"generativeAI_customInputs": ""' not in text, \
        "say-node must not document generativeAI_customInputs as empty string"


def test_node_types_references_say_node_topic(mock_client, state, cache):
    """node-types must cross-reference say-node topic for config schema."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "say-node" in text, \
        'node-types must reference explain("say-node") for say node config schema'


# ── Issue #37: turn-structure contradicts node-positioning on Once branch insertion ──

def test_turn_structure_once_branch_uses_append_not_appendchild(mock_client, state, cache):
    """turn-structure must document mode='append' for Once branch population, not mode='appendChild'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "turn-structure"})
    text = result[0].text
    assert 'mode="appendChild"' not in text, \
        "turn-structure must not document appendChild for Once branches (contradicts node-positioning)"
    assert 'mode="append"' in text, \
        "turn-structure must document mode='append' for branch population"
    assert "onfirst" in text.lower(), \
        "turn-structure must show branch marker _id as the append target"
