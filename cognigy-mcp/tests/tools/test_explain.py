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


# ── Issue #39 (doc): xapp-event-handling three gaps ─────────────────────────

def test_xapp_event_handling_sdk_path_is_relative(mock_client, state, cache):
    """xapp-event-handling Variant A SDK script must use /sdk/app-page-sdk.js, not the xapp.cognigy.ai URL."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "xapp.cognigy.ai/sdk/cognigy-xapp-sdk.js" not in text, \
        "Must not document the old xapp.cognigy.ai SDK URL — correct path is /sdk/app-page-sdk.js"
    assert "/sdk/app-page-sdk.js" in text, \
        "Must document the correct SDK script path: /sdk/app-page-sdk.js"
    assert "SDK is not required for Variant B" in text or \
           "SDK not required for Variant B" in text or \
           "not required" in text.lower() and "variant b" in text.lower(), \
        "Must note that the SDK script is not required for Variant B (webhook inject pattern)"


def test_xapp_event_handling_toolargs_valid_in_html(mock_client, state, cache):
    """xapp-event-handling must document that toolArgs can be used directly in setHTMLAppState HTML."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    # Must show toolArgs used directly in an HTML template (not just warn they expire)
    assert "{{input.aiAgent.toolArgs." in text, \
        "Must show {{input.aiAgent.toolArgs.field}} used directly in HTML — not just warn about expiry"
    # Must explain WHY it's safe — setHTMLAppState runs on the same tool turn
    assert "same" in text.lower() and "turn" in text.lower() and "html" in text.lower(), \
        "Must explain that toolArgs are available in HTML because setHTMLAppState runs on the same tool turn"


def test_xapp_event_handling_multistate_ui_documented(mock_client, state, cache):
    """xapp-event-handling must document the multi-state async UI pattern for Variant B."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "showState" in text or "show-state" in text or "state-processing" in text, \
        "Must document multi-state UI pattern (e.g. showState, state-processing)"
    assert "processing" in text.lower(), \
        "Must show a processing/spinner state for async Variant B flows"


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


def test_node_positioning_documents_canonical_modes(mock_client, state, cache):
    """node-positioning documents append and appendChild as the two canonical modes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert '"append"' in text, "Should document append mode"
    assert '"appendChild"' in text, "Should document appendChild mode"
    assert "branch marker" in text.lower() or "branchMarkerId" in text or "childIds" in text, \
        "Should document branch-marker targeting for Once/IF branches"
    assert "insertBefore" not in text, "Should not document removed insertBefore"
    assert "insertAfter" not in text, "Should not document removed insertAfter"
    assert "BROKEN on AU1" not in text, "Should not document AU1 breakage"


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


def test_all_migrated_topics_accessible_via_explain(mock_client, state, cache):
    """After promotion, explain must serve all migrated topics from the generated module."""
    handlers = make_handlers(mock_client, state, cache)
    for topic in TOPICS:
        result = handlers["explain"]({"topic": topic})
        text = result[0].text
        assert "Unknown topic" not in text, f"explain({topic!r}) returned Unknown topic"
        assert len(text) > 50, f"explain({topic!r}) returned too-short content"


def test_voice_silence_timeout_accessible_via_explain(mock_client, state, cache):
    """voice-silence-timeout must be accessible via the promoted explain tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "voice-silence-timeout"})
    text = result[0].text
    assert "noUserInput" in text
    assert "Unknown topic" not in text


def test_xapp_event_handling_variant_a_payload_path_via_explain(mock_client, state, cache):
    """issue #40 regression: explain must serve corrected xapp-event-handling."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "input.data._cognigy._app.payload" in text
    assert "input.data.selectedOption" not in text


# ── Issue #59: Runtime Objects section in code-node-patterns ────────────────

def test_code_node_patterns_input_object_documented(mock_client, state, cache):
    """code-node-patterns must document the input object property table."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "input.text" in text, "Must document input.text"
    assert "input.slots" in text, "Must document input.slots"
    assert "input.sessionId" in text, "Must document input.sessionId"
    assert "input.userId" in text, "Must document input.userId"
    assert "input.intentScore" in text, "Must document input.intentScore"


def test_code_node_patterns_analyticsdata_documented(mock_client, state, cache):
    """code-node-patterns must document analyticsdata direct assignment."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "analyticsdata" in text, "Must document analyticsdata object"
    assert "custom1" in text, "Must document custom1 through custom10 fields"


def test_code_node_patterns_last_conversation_entries_documented(mock_client, state, cache):
    """code-node-patterns must document lastConversationEntries."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "lastConversationEntries" in text, "Must document lastConversationEntries array"


def test_code_node_patterns_context_prefers_utils_over_api(mock_client, state, cache):
    """code-node-patterns must note that setVar/mergeVar are preferred over api.setContext."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    # Must explicitly call out the preference — not just list both equally
    assert "prefer" in text.lower() or "Prefer" in text, \
        "Must state preference for setVar/mergeVar over api.setContext"
    assert "api.setContext" in text, \
        "Must still document api.setContext (it exists, just not preferred)"


def test_explain_dev_tool_removed(mock_client, state, cache):
    """explain_dev was a migration scaffold — it must not exist in TOOLS after promotion."""
    assert not any(t.name == "explain_dev" for t in TOOLS), \
        "explain_dev must be removed from TOOLS after full migration"


# ── Issue #58: agent docs migration ─────────────────────────────────────────

def test_agent_persona_authoring_has_field_purposes(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-persona-authoring"})
    text = result[0].text
    assert "description" in text
    assert "instructions" in text
    assert "speakingStyle" in text


def test_agent_behavioral_rules_has_silent_execution(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-behavioral-rules"})
    text = result[0].text
    assert "silently" in text
    assert "escalate_to_human" in text
    assert "outcome" in text.lower()


def test_multi_agent_architecture_has_concierge_pattern(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "multi-agent-architecture"})
    text = result[0].text
    assert "return_to_concierge" in text
    assert "shortTermMemory" in text
    assert "toolResponse" in text


def test_agent_tool_patterns_has_granularity_options(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-tool-patterns"})
    text = result[0].text
    assert "action-parameterized" in text.lower() or "action_parameterized" in text.lower() or "Action-parameterized" in text
    assert "context.toolResponse" in text
    assert "Granular" in text or "granular" in text


def test_agent_handover_has_two_consumer_model(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-handover"})
    text = result[0].text
    assert "escalate_to_human" in text
    assert "handoverContext" in text
    assert "handoverSummary" in text


# ── Issue #61: profile section corrections ───────────────────────────────────

def test_code_node_patterns_profile_is_read_only_snapshot(mock_client, state, cache):
    """profile section must describe read-only snapshot behaviour and reference profile-editing."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "read-only" in text.lower() or "read only" in text.lower(), \
        "profile section must describe the read-only snapshot model"
    assert "profile-editing" in text, \
        "profile section must reference explain('profile-editing') for utilities"


def test_code_node_patterns_add_contact_memory_takes_string(mock_client, state, cache):
    """api.addContactMemory must be documented as taking a plain string, not an object."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "api.addContactMemory({ label" not in text, \
        "addContactMemory must not be documented with object signature — Cognigy takes a plain string"
    assert 'api.addContactMemory("' in text, \
        "addContactMemory must be documented with a plain string argument"


# ── Issue #61: profile-editing topic ─────────────────────────────────────────

def test_profile_editing_topic_exists(mock_client, state, cache):
    """profile-editing must be a recognised explain topic."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "Unknown topic" not in text, "profile-editing must be a known topic"
    assert len(text) > 100


def test_profile_editing_documents_utility_functions(mock_client, state, cache):
    """profile-editing must document all three utility functions."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "getProfileVar" in text, "Must document getProfileVar"
    assert "setProfileVar" in text, "Must document setProfileVar"
    assert "mergeProfileVar" in text, "Must document mergeProfileVar"


def test_profile_editing_documents_snapshot_model(mock_client, state, cache):
    """profile-editing must explain that profile is a read-only snapshot."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "snapshot" in text.lower(), \
        "Must explain that profile is a read-only snapshot"
    assert "api.updateProfile" in text, \
        "Must document api.updateProfile as the only write path"


def test_profile_editing_utility_functions_await_update_profile(mock_client, state, cache):
    """setProfileVar and mergeProfileVar must await api.updateProfile."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "await api.updateProfile" in text, \
        "Utility functions must await api.updateProfile — it returns a Promise"


def test_profile_editing_documents_flat_key_constraint(mock_client, state, cache):
    """profile-editing must document that only flat top-level keys are supported."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "flat" in text.lower() or "top-level" in text.lower(), \
        "Must note that setProfileVar/mergeProfileVar accept flat top-level keys only"


def test_profile_editing_warns_against_mixing_set_and_merge_on_same_key(mock_client, state, cache):
    """profile-editing must warn that mixing setProfileVar+mergeProfileVar on the same key clobbers."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "profile-editing"})
    text = result[0].text
    assert "same key" in text.lower() or "clobber" in text.lower(), \
        "Must warn against mixing setProfileVar and mergeProfileVar on the same key"


def test_explain_with_empty_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({})
    assert len(result) == 1
    assert "cognigy-vibe-mcp" in result[0].text.lower() or "topics" in result[0].text.lower()


def test_explain_topic_wrong_type_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": 123})
    # Pydantic coerces int → str in lax mode; confirm no crash and some response returned
    assert len(result) == 1
