import pytest
from cognigy_mcp.tools.explain import TOOLS, make_handlers
from cognigy_mcp.tools._explain_topics_generated import TOPICS as DEV_TOPICS


def test_explain_dev_tool_exported():
    assert any(t.name == "explain_dev" for t in TOOLS)


def test_explain_dev_tool_description_contains_all_topic_names():
    tool = next(t for t in TOOLS if t.name == "explain_dev")
    for topic in DEV_TOPICS:
        assert topic in tool.description, f"Topic '{topic}' missing from explain_dev description"


def test_explain_dev_no_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({})
    text = result[0].text
    assert "Topics" in text
    for topic in DEV_TOPICS:
        assert topic in text, f"Topic '{topic}' missing from orientation index"


def test_explain_dev_known_topic_returns_content(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for topic in DEV_TOPICS:
        result = handlers["explain_dev"]({"topic": topic})
        text = result[0].text
        assert len(text) > 100, f"Topic '{topic}' returned too-short content: {text!r}"
        assert "Unknown topic" not in text, f"Topic '{topic}' was not found"


def test_explain_dev_xapp_primer_mentions_variants(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "xapp"})
    text = result[0].text
    assert "Variant A" in text
    assert "Variant B" in text


def test_explain_dev_unknown_topic_returns_error_with_available_topics(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "node-positioning"})
    text = result[0].text
    assert "node-positioning" in text          # echoes the bad topic name
    assert "code-node-patterns" in text        # lists what IS available


def test_explain_dev_does_not_serve_legacy_content(mock_client, state, cache):
    """explain_dev must return an error for topics that only exist in the legacy explain tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "node-positioning"})
    text = result[0].text
    assert "Unknown topic" in text
    # Legacy content for node-positioning starts with this heading
    assert "Inserting and Moving Nodes" not in text


def test_existing_explain_tool_unchanged(mock_client, state, cache):
    """Existing explain tool must still work after explain_dev is added."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "append" in text
    assert "Unknown topic" not in text
