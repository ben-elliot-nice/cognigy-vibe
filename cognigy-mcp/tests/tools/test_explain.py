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
