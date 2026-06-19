# cognigy-mcp/tests/tools/test_init_tool.py
import os
from pathlib import Path
import pytest
import mcp.types as types
from cognigy_mcp.tools import init_tool


def test_tools_list_has_one_tool():
    assert len(init_tool.TOOLS) == 1
    assert init_tool.TOOLS[0].name == "init"


def test_tools_schema_requires_url_and_key():
    schema = init_tool.TOOLS[0].inputSchema
    assert "cognigy_base_url" in schema["required"]
    assert "cognigy_api_key" in schema["required"]
    assert "cognigy_project_id" not in schema["required"]


def test_make_handlers_returns_init_key():
    handlers = init_tool.make_handlers()
    assert "init" in handlers


def test_init_writes_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handlers = init_tool.make_handlers()

    # patch os._exit so the test doesn't actually exit
    exited_with = []
    monkeypatch.setattr(os, "_exit", lambda code: exited_with.append(code))

    # also patch threading.Timer to call immediately (synchronously)
    import threading
    class _ImmediateTimer:
        def __init__(self, delay, fn):
            self._fn = fn
        def start(self):
            self._fn()
    monkeypatch.setattr(threading, "Timer", _ImmediateTimer)

    result = handlers["init"]({
        "cognigy_base_url": "https://cognigy-api-au1.nicecxone.com",
        "cognigy_api_key": "test-key-123",
    })

    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com" in content
    assert "COGNIGY_API_KEY=test-key-123" in content
    assert "COGNIGY_PROJECT_ID" not in content
    assert exited_with == [42]


def test_init_writes_project_id_when_provided(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handlers = init_tool.make_handlers()

    import threading
    class _ImmediateTimer:
        def __init__(self, delay, fn):
            self._fn = fn
        def start(self):
            self._fn()
    monkeypatch.setattr(threading, "Timer", _ImmediateTimer)
    monkeypatch.setattr(os, "_exit", lambda code: None)

    handlers["init"]({
        "cognigy_base_url": "https://cognigy-api-au1.nicecxone.com",
        "cognigy_api_key": "test-key-123",
        "cognigy_project_id": "proj-abc",
    })

    content = (tmp_path / ".env").read_text()
    assert "COGNIGY_PROJECT_ID=proj-abc" in content


def test_init_strips_trailing_slash_from_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handlers = init_tool.make_handlers()

    import threading
    class _ImmediateTimer:
        def __init__(self, delay, fn):
            self._fn = fn
        def start(self):
            self._fn()
    monkeypatch.setattr(threading, "Timer", _ImmediateTimer)
    monkeypatch.setattr(os, "_exit", lambda code: None)

    handlers["init"]({
        "cognigy_base_url": "https://cognigy-api-au1.nicecxone.com/",
        "cognigy_api_key": "key",
    })

    content = (tmp_path / ".env").read_text()
    assert "COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com\n" in content


def test_init_returns_text_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handlers = init_tool.make_handlers()

    import threading
    class _ImmediateTimer:
        def __init__(self, delay, fn):
            self._fn = fn
        def start(self):
            self._fn()
    monkeypatch.setattr(threading, "Timer", _ImmediateTimer)
    monkeypatch.setattr(os, "_exit", lambda code: None)

    result = handlers["init"]({"cognigy_base_url": "https://x.com", "cognigy_api_key": "k"})
    assert isinstance(result, list)
    assert result[0].type == "text"
    assert len(result[0].text) > 0
