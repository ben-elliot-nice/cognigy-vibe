import json
import pytest
from pathlib import Path
from cognigy_mcp.tools.file_push import make_handlers, TOOLS


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    assert "push_code_node" in names
    assert "push_html_node" in names
    assert "push_tool_from_file" in names


def test_push_code_node_first_push(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("api.say('hello');")
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": ""}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "api.say('hello');"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script),
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert cache.get_node_snapshot("node-1") == "api.say('hello');"


def test_push_code_node_no_conflict(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("new content")
    cache.set_node_snapshot("node-1", "old content")
    # Remote matches snapshot (no UI edits)
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": "old content"}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "new content"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script), "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_code_node_conflict_blocked(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("my new code")
    cache.set_node_snapshot("node-1", "original")
    # Remote has been edited in UI (differs from snapshot)
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": "edited in UI"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script), "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "conflict" in data
    mock_client.patch.assert_not_called()


def test_push_code_node_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": "/nonexistent/file.js", "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_html_node(mock_client, state, cache, tmp_path):
    html_file = tmp_path / "page.html"
    html_file.write_text("<h1>Hello</h1>")
    mock_client.patch.return_value = {"_id": "node-2", "config": {"html": "<h1>Hello</h1>", "mode": "full"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_html_node"]({
        "html_file": str(html_file), "node_id": "node-2", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["mode"] == "full"


def test_push_tool_from_file_create(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "my_tool.json"
    tool_def = {"name": "my_tool", "description": "Does stuff", "parameters": []}
    tool_file.write_text(json.dumps(tool_def))
    mock_client.post.return_value = {"_id": "tool-1", **tool_def}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_tool_from_file"]({
        "file": str(tool_file), "project_id": "proj-1",
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "tool-1"


def test_push_code_node_patch_failure_returns_error(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("some code")
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": "some code"}}
    mock_client.patch.side_effect = Exception("network error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script), "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    # Snapshot should NOT be updated on failed push
    assert cache.get_node_snapshot("node-1") is None


def test_push_tool_from_file_invalid_json(mock_client, state, cache, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json {")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_tool_from_file"]({"file": str(bad_file), "project_id": "proj-1"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_code_node_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "payment.js").write_text("api.say('hello');")
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": ""}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "api.say('hello');"}}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_code_node"]({
        "workspace_file": "payment.js",
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_code_node_workspace_file_not_found(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_code_node"]({
        "workspace_file": "missing.js",
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_code_node_no_path_arg_returns_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({"node_id": "node-1", "flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_code_node_workspace_file_without_workspace_dir(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)  # no workspace_dir
    result = handlers["push_code_node"]({
        "workspace_file": "payment.js",
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "remote" in data["error"].lower()


def test_push_html_node_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "page.html").write_text("<h1>Hi</h1>")
    mock_client.patch.return_value = {"_id": "node-2"}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_html_node"]({
        "workspace_file": "page.html",
        "node_id": "node-2",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_tool_from_file_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    tool_def = {"name": "my_tool", "description": "desc", "parameters": []}
    (workspace_dir / "tool.json").write_text(json.dumps(tool_def))
    mock_client.post.return_value = {"_id": "tool-1", **tool_def}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_tool_from_file"]({
        "workspace_file": "tool.json",
        "project_id": "proj-1",
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "tool-1"
