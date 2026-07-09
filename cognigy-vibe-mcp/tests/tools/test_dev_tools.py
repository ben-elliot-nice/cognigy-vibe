import os
import threading
import pytest
import mcp.types as types
from cognigy_mcp.tools import dev_tools


def test_tools_list_has_reload_mcp():
    assert len(dev_tools.TOOLS) == 1
    assert dev_tools.TOOLS[0].name == "reload_mcp"


def test_tools_schema_accepts_no_args():
    schema = dev_tools.TOOLS[0].inputSchema
    assert schema.get("required", []) == []


def test_make_handlers_returns_reload_mcp_key():
    handlers = dev_tools.make_handlers()
    assert "reload_mcp" in handlers


def test_reload_mcp_returns_text_and_exits_42(monkeypatch):
    exited_with = []
    monkeypatch.setattr(os, "_exit", lambda code: exited_with.append(code))

    class _ImmediateTimer:
        def __init__(self, delay, fn):
            self._fn = fn
        def start(self):
            self._fn()
    monkeypatch.setattr(threading, "Timer", _ImmediateTimer)

    handlers = dev_tools.make_handlers()
    result = handlers["reload_mcp"]({})

    assert isinstance(result, list)
    assert result[0].type == "text"
    assert exited_with == [42]
