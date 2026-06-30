import json
import pytest
from pathlib import Path
from cognigy_mcp.tools.file_push import make_handlers, TOOLS


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    assert "push_code_node" in names
    assert "push_html_node" in names


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
    mock_client.get.return_value = {"_id": "node-2", "config": {"html": "", "mode": "url"}}
    mock_client.patch.return_value = {"_id": "node-2", "config": {"html": "<h1>Hello</h1>", "mode": "full"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_html_node"]({
        "html_file": str(html_file), "node_id": "node-2", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["mode"] == "full"


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


def test_push_code_node_create_new_node(mock_client, state, cache, tmp_path):
    script = tmp_path / "init.js"
    script.write_text("api.say('hello');")
    mock_client.post.return_value = {"_id": "node-new", "type": "code", "label": "Init"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script),
        "flow_id": "flow-1",
        "mode": "append",
        "target": "node-start",
        "label": "Init",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["created"] is True
    assert data["node_id"] == "node-new"
    assert cache.get_node_snapshot("node-new") == "api.say('hello');"
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["type"] == "code"
    assert posted_body["mode"] == "append"
    assert posted_body["target"] == "node-start"
    assert posted_body["extension"] == "@cognigy/basic-nodes"
    assert posted_body["config"]["code"] == "api.say('hello');"


def test_push_code_node_create_missing_mode_or_target(mock_client, state, cache, tmp_path):
    script = tmp_path / "init.js"
    script.write_text("api.say('hello');")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script),
        "flow_id": "flow-1",
        "mode": "append",
        # target omitted
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_code_node_create_post_failure(mock_client, state, cache, tmp_path):
    script = tmp_path / "init.js"
    script.write_text("api.say('hello');")
    mock_client.post.side_effect = Exception("api error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script),
        "flow_id": "flow-1",
        "mode": "append",
        "target": "node-start",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_code_node_create_saves_to_state(mock_client, state, cache, tmp_path):
    """push_code_node creation path must add the new node to state so resolve_resource('nodes', ...) works."""
    script = tmp_path / "init.js"
    script.write_text("api.say('hello');")
    mock_client.post.return_value = {"_id": "node-new", "type": "code", "label": "Init"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_code_node"]({
        "script_file": str(script),
        "flow_id": "flow-1",
        "mode": "append",
        "target": "node-start",
        "label": "Init",
    })
    entry = state.get("nodes", "Init")
    assert entry is not None, "Node not found in state after push_code_node creation"
    assert entry["id"] == "node-new"
    assert entry["flowId"] == "flow-1"


# ---------------------------------------------------------------------------
# push_agent_tool tests
# ---------------------------------------------------------------------------

def test_push_agent_tool_exported():
    names = [t.name for t in TOOLS]
    assert "push_agent_tool" in names


def test_push_agent_tool_create_bare_minimum(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "end_call.tool.json"
    tool_file.write_text('{"toolId": "end_call", "description": "End the call."}')
    mock_client.post.return_value = {"_id": "tool-node-1", "type": "aiAgentJobTool", "label": "end_call"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["created"] is True
    assert data["node_id"] == "tool-node-1"
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["type"] == "aiAgentJobTool"
    assert posted_body["extension"] == "@cognigy/basic-nodes"
    assert posted_body["mode"] == "appendChild"
    assert posted_body["target"] == "job-1"
    assert posted_body["config"]["toolId"] == "end_call"
    assert posted_body["config"]["description"] == "End the call."
    assert posted_body["config"]["useParameters"] is False
    assert posted_body["config"]["debugMessage"] is True
    assert posted_body["config"]["condition"] == ""


def test_push_agent_tool_create_label_defaults_to_tool_id(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "check_balance", "description": "Check balance."}')
    mock_client.post.return_value = {"_id": "tool-node-2", "type": "aiAgentJobTool", "label": "check_balance"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["label"] == "check_balance"


def test_push_agent_tool_create_label_from_file(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "check_balance", "label": "Check Balance", "description": "Check balance."}')
    mock_client.post.return_value = {"_id": "tool-node-3", "type": "aiAgentJobTool", "label": "Check Balance"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["label"] == "Check Balance"


def test_push_agent_tool_create_with_parameters(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "check.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "check_balance",
        "description": "Check balance.",
        "parameters": {
            "type": "object",
            "properties": {"account_type": {"type": "string", "description": "Savings or current"}},
            "required": ["account_type"],
            "additionalProperties": False,
        }
    }))
    mock_client.post.return_value = {"_id": "tool-node-4", "type": "aiAgentJobTool", "label": "check_balance"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["config"]["useParameters"] is True
    # parameters must be a JSON string, not an object
    params_value = posted_body["config"]["parameters"]
    assert isinstance(params_value, str)
    params_parsed = json.loads(params_value)
    assert params_parsed["properties"]["account_type"]["type"] == "string"


def test_push_agent_tool_create_with_condition(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "sensitive_action",
        "description": "Sensitive action.",
        "condition": "context.authVerified",
    }))
    mock_client.post.return_value = {"_id": "tool-node-5", "type": "aiAgentJobTool", "label": "sensitive_action"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["config"]["condition"] == "context.authVerified"


def test_push_agent_tool_create_saves_to_state(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.post.return_value = {"_id": "tool-node-6", "type": "aiAgentJobTool", "label": "my_tool"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    entry = state.get("nodes", "my_tool")
    assert entry is not None
    assert entry["id"] == "tool-node-6"
    assert entry["flowId"] == "flow-1"


def test_push_agent_tool_create_missing_job_node_id(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_update(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Updated description."}')
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "node_id": "tool-node-existing",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data.get("updated") is True
    mock_client.post.assert_not_called()
    patch_path = mock_client.patch.call_args[0][0]
    assert "tool-node-existing" in patch_path
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["description"] == "Updated description."
    assert patch_body["config"]["debugMessage"] is True
    assert patch_body["config"]["condition"] == ""


def test_push_agent_tool_update_parameters_serialized(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "my_tool",
        "description": "Does things.",
        "parameters": {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"], "additionalProperties": False},
    }))
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "node_id": "tool-node-existing"})
    patch_body = mock_client.patch.call_args[0][1]
    assert isinstance(patch_body["config"]["parameters"], str)
    assert patch_body["config"]["useParameters"] is True


def test_push_agent_tool_update_with_condition(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "sensitive_tool",
        "description": "Sensitive operation.",
        "condition": "context.authVerified",
    }))
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "node_id": "tool-node-existing",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["condition"] == "context.authVerified"


def test_push_agent_tool_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": "/nonexistent/tool.tool.json",
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_missing_required_fields(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool"}')  # missing description
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_create_api_failure(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.post.side_effect = Exception("network error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_agent_tool_update_api_failure(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.patch.side_effect = Exception("api error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "node_id": "tool-node-existing"})
    data = json.loads(result[0].text)
    assert "error" in data


import struct

# ---------------------------------------------------------------------------
# push_agent_avatar helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int, height: int) -> bytes:
    """Produce minimal PNG bytes with correct signature and IHDR dimensions."""
    sig = b'\x89PNG\r\n\x1a\n'
    # IHDR: 4 bytes length + 4 bytes type + 13 bytes data + 4 bytes CRC
    ihdr_data = struct.pack('>II', width, height) + b'\x08\x02\x00\x00\x00'
    ihdr_type = b'IHDR'
    import zlib
    crc = struct.pack('>I', zlib.crc32(ihdr_type + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack('>I', 13) + ihdr_type + ihdr_data + crc
    iend = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    return sig + ihdr + iend


# ---------------------------------------------------------------------------
# push_agent_avatar tests
# ---------------------------------------------------------------------------

def test_push_agent_avatar_exported():
    names = [t.name for t in TOOLS]
    assert "push_agent_avatar" in names


def test_push_agent_avatar_success(mock_client, state, cache, tmp_path):
    img = tmp_path / "avatar_optimized.png"
    img.write_bytes(_make_png_bytes(136, 184))
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": str(img),
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["agent_id"] == "agent-abc"
    assert data["bytes"] == len(img.read_bytes())
    patch_path, patch_body = mock_client.patch.call_args[0]
    assert "agent-abc" in patch_path
    assert patch_body["imageOptimizedFormat"] is True
    assert patch_body["image"].startswith("data:image/png;base64,")


def test_push_agent_avatar_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": "/nonexistent/avatar.png",
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.patch.assert_not_called()


def test_push_agent_avatar_not_png(mock_client, state, cache, tmp_path):
    img = tmp_path / "avatar.jpg"
    img.write_bytes(b'\xff\xd8\xff' + b'\x00' * 30)  # JPEG magic bytes
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": str(img),
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.patch.assert_not_called()


def test_push_agent_avatar_wrong_dimensions_correct_ratio(mock_client, state, cache, tmp_path):
    # 272x368 = 2× the spec, same 17:23 ratio
    img = tmp_path / "avatar_optimized.png"
    img.write_bytes(_make_png_bytes(272, 368))
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": str(img),
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "272" in data["error"]
    assert "resize to 136×184" in data["error"]
    mock_client.patch.assert_not_called()


def test_push_agent_avatar_wrong_dimensions_wrong_ratio(mock_client, state, cache, tmp_path):
    img = tmp_path / "avatar_optimized.png"
    img.write_bytes(_make_png_bytes(200, 200))
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": str(img),
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "200" in data["error"]
    assert "Expected 136×184" in data["error"]
    mock_client.patch.assert_not_called()


def test_push_agent_avatar_api_failure(mock_client, state, cache, tmp_path):
    img = tmp_path / "avatar_optimized.png"
    img.write_bytes(_make_png_bytes(136, 184))
    mock_client.patch.side_effect = Exception("network error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({
        "image_file": str(img),
        "agent_id": "agent-abc",
    })
    data = json.loads(result[0].text)
    assert "error" in data

