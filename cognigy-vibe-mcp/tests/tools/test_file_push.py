import json
import struct
import zlib
import pytest
from pathlib import Path
from unittest.mock import patch, call
from cognigy_mcp.tools.file_push import make_handlers, TOOLS
from cognigy_mcp.api import ApiError


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


# ---------------------------------------------------------------------------
# push_agent_avatar helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int, height: int) -> bytes:
    """Produce minimal PNG bytes with correct signature and IHDR dimensions."""
    sig = b'\x89PNG\r\n\x1a\n'
    # IHDR: 4 bytes length + 4 bytes type + 13 bytes data + 4 bytes CRC
    ihdr_data = struct.pack('>II', width, height) + b'\x08\x02\x00\x00\x00'
    ihdr_type = b'IHDR'
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


def test_push_agent_avatar_truncated_png(mock_client, state, cache, tmp_path):
    img = tmp_path / "truncated.png"
    img.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00')  # valid magic, no IHDR
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_avatar"]({"image_file": str(img), "agent_id": "agent-abc"})
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.patch.assert_not_called()


# ---------------------------------------------------------------------------
# export_package tests
#
# Corrected API flow:
#   1. GET  /v2.0/flows?projectId=...                 → {items: [{_id: flow_id}, ...]} (resourceIds source)
#   2. POST /v2.0/packages                            → Task {_id: task_id, status: "queued"}
#   3. GET  /v2.0/tasks/{taskId}                      → Task {status: "done"|"error"|"cancelled"|...}
#   4. GET  /v2.0/packages?projectId=...&sort=...     → {items: [{_id: package_id, ...}]}
#   5. POST /v2.0/packages/{packageId}/downloadlink   → {downloadLink: "https://..."}
#   6. client.download_url("https://...")             → zip bytes (pre-signed URL, not API path)
# ---------------------------------------------------------------------------

_FLOWS_RESPONSE = {"items": [{"_id": "flow-1"}], "total": 1}


def _make_export_mocks(mock_client, task_id, task_status_seq, package_id, zip_bytes,
                       task_error=None, fail_reason=None):
    """Wire up mock_client for a standard export_package run.

    task_status_seq: list of status strings returned by successive GET /v2.0/tasks calls.
    """
    mock_client.post.side_effect = [
        # POST /v2.0/packages — returns Task
        {"_id": task_id, "status": "queued"},
        # POST /v2.0/packages/{packageId}/downloadlink — returns download link
        {"downloadLink": "https://storage.example.com/packages/export.zip"},
    ]
    task_responses = []
    for s in task_status_seq:
        resp = {"_id": task_id, "status": s}
        if s == "error" and fail_reason:
            resp["failReason"] = fail_reason
        task_responses.append(resp)
    mock_client.get.side_effect = [
        # GET /v2.0/flows — resolves resourceIds
        _FLOWS_RESPONSE,
    ] + task_responses + [
        # GET /v2.0/packages (list) — called once after task is done
        {"items": [{"_id": package_id, "name": "export"}], "total": 1},
    ]
    mock_client.download_url.return_value = zip_bytes


def test_export_package_exported():
    names = [t.name for t in TOOLS]
    assert "export_package" in names


def test_export_package_happy_path_first_poll(mock_client, state, cache, tmp_path):
    """Task is done on the first poll — writes zip and returns success."""
    zip_bytes = b"PK\x03\x04fake-zip"
    _make_export_mocks(mock_client, "task-1", ["done"], "pkg-1", zip_bytes)
    out = tmp_path / "export.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-1",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["task_id"] == "task-1"
    assert data["package_id"] == "pkg-1"
    assert data["bytes"] == len(zip_bytes)
    assert out.read_bytes() == zip_bytes
    # Verify correct endpoint sequence
    mock_client.post.assert_any_call(
        "/v2.0/packages", {"projectId": "proj-1", "name": "export", "resourceIds": ["flow-1"]}
    )
    mock_client.get.assert_any_call("/v2.0/tasks/task-1")
    mock_client.post.assert_any_call("/v2.0/packages/pkg-1/downloadlink", {})
    mock_client.download_url.assert_called_once_with(
        "https://storage.example.com/packages/export.zip"
    )


def test_export_package_multi_poll(mock_client, state, cache, tmp_path):
    """Task is queued/active on first two polls then done — handler waits correctly."""
    zip_bytes = b"PK\x03\x04another-zip"
    _make_export_mocks(mock_client, "task-2", ["queued", "active", "done"], "pkg-2", zip_bytes)
    out = tmp_path / "out.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-2",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert data["success"] is True
    # 1 flows lookup + 3 task polls + 1 package list = 5 GET calls
    assert mock_client.get.call_count == 5


def test_export_package_task_failure(mock_client, state, cache, tmp_path):
    """Task reports status='error' — handler returns error without downloading."""
    mock_client.post.return_value = {"_id": "task-3", "status": "queued"}
    mock_client.get.side_effect = [
        _FLOWS_RESPONSE,
        {"_id": "task-3", "status": "error", "failReason": "export failed"},
    ]
    out = tmp_path / "nope.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-3",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "export failed" in data["error"]
    mock_client.download_url.assert_not_called()
    assert not out.exists()


def test_export_package_task_cancelled(mock_client, state, cache, tmp_path):
    """Task is cancelled — handler returns error immediately rather than timing out."""
    mock_client.post.return_value = {"_id": "task-c", "status": "queued"}
    mock_client.get.side_effect = [
        _FLOWS_RESPONSE,
        {"_id": "task-c", "status": "cancelled"},
    ]
    out = tmp_path / "cancelled.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-c",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "cancelled" in data["error"]
    mock_client.download_url.assert_not_called()
    assert not out.exists()


def test_export_package_task_cancelling(mock_client, state, cache, tmp_path):
    """Task is in cancelling state — treated as terminal, not as transient."""
    mock_client.post.return_value = {"_id": "task-cc", "status": "queued"}
    mock_client.get.side_effect = [
        _FLOWS_RESPONSE,
        {"_id": "task-cc", "status": "cancelling"},
    ]
    out = tmp_path / "cancelling.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-cc",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "cancelling" in data["error"]
    mock_client.download_url.assert_not_called()


def test_export_package_timeout(mock_client, state, cache, tmp_path):
    """Task never completes — handler returns a timeout error."""
    import cognigy_mcp.tools.file_push as fp_module
    mock_client.post.return_value = {"_id": "task-4", "status": "queued"}
    mock_client.get.side_effect = [_FLOWS_RESPONSE] + [
        {"_id": "task-4", "status": "active"} for _ in range(10)
    ]
    out = tmp_path / "timeout.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"), \
         patch.object(fp_module, "_EXPORT_TIMEOUT", 0.0):
        result = handlers["export_package"]({
            "project_id": "proj-4",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "timed out" in data["error"]
    mock_client.download_url.assert_not_called()


def test_export_package_post_api_error(mock_client, state, cache, tmp_path):
    """POST /v2.0/packages fails — handler returns error immediately."""
    mock_client.get.return_value = _FLOWS_RESPONSE
    mock_client.post.side_effect = Exception("network error")
    out = tmp_path / "fail.zip"
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["export_package"]({
        "project_id": "proj-5",
        "output_path": str(out),
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "network error" in data["error"]
    mock_client.download_url.assert_not_called()


def test_export_package_parent_dir_auto_created(mock_client, state, cache, tmp_path):
    """output_path parent directories are created automatically."""
    zip_bytes = b"PK\x03\x04zip-content"
    _make_export_mocks(mock_client, "task-6", ["done"], "pkg-6", zip_bytes)
    # Deep nested path that does not exist yet
    out = tmp_path / "Demo Builds" / "acme-demo" / "acme-package.zip"
    assert not out.parent.exists()
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        result = handlers["export_package"]({
            "project_id": "proj-6",
            "output_path": str(out),
        })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert out.exists()
    assert out.read_bytes() == zip_bytes


def test_export_package_polls_task_endpoint_not_packages(mock_client, state, cache, tmp_path):
    """Polling must use GET /v2.0/tasks/{taskId}, not GET /v2.0/packages/{taskId}."""
    zip_bytes = b"PK\x03\x04zip"
    _make_export_mocks(mock_client, "task-7", ["done"], "pkg-7", zip_bytes)
    out = tmp_path / "poll-check.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        handlers["export_package"]({"project_id": "proj-7", "output_path": str(out)})
    # All GET calls that are not the final package list must be to /v2.0/tasks/
    task_get_calls = [c for c in mock_client.get.call_args_list
                      if c[0][0].startswith("/v2.0/tasks/")]
    assert len(task_get_calls) >= 1
    # No GET call should target /v2.0/packages/<task-id>
    pkg_poll_calls = [c for c in mock_client.get.call_args_list
                      if "/v2.0/packages/task-" in c[0][0]]
    assert len(pkg_poll_calls) == 0


def test_export_package_download_uses_presigned_url(mock_client, state, cache, tmp_path):
    """Download must use download_url() with the pre-signed URI, not a relative API path."""
    zip_bytes = b"PK\x03\x04zip"
    _make_export_mocks(mock_client, "task-8", ["done"], "pkg-8", zip_bytes)
    out = tmp_path / "presigned-check.zip"
    handlers = make_handlers(mock_client, state, cache)
    with patch("cognigy_mcp.tools.file_push.time.sleep"):
        handlers["export_package"]({"project_id": "proj-8", "output_path": str(out)})
    # download_url must be called with an absolute URL
    assert mock_client.download_url.call_count == 1
    url_arg = mock_client.download_url.call_args[0][0]
    assert url_arg.startswith("https://"), f"Expected absolute URL, got: {url_arg}"


def test_push_code_node_missing_script_file_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({"flow_id": "flow-1"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "script_file" for d in data["details"])


def test_push_html_node_missing_flow_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_html_node"]({"html_file": "/tmp/x.html", "node_id": "node-1"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "flow_id" for d in data["details"])


def test_export_package_missing_output_path_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["export_package"]({"project_id": "proj-1"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "output_path" for d in data["details"])


# ---------------------------------------------------------------------------
# push_knowledge_source_file tests
# ---------------------------------------------------------------------------

def test_push_knowledge_source_file_exported():
    names = [t.name for t in TOOLS]
    assert "push_knowledge_source_file" in names


def test_push_knowledge_source_file_success(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.txt"
    doc.write_text("The battery trade-in policy allows...")
    mock_client.post_multipart.return_value = {"_id": "task-1", "status": "queued"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["task_id"] == "task-1"
    assert data["status"] == "queued"
    call = mock_client.post_multipart.call_args
    assert call[0][0] == "/v2.0/knowledgestores/ks-1/sources/upload"
    files = call[1]["files"]
    assert files["file"][0] == "policy.txt"
    assert files["file"][1] == b"The battery trade-in policy allows..."
    assert files["file"][2] == "text/plain"
    assert "data" not in call[1] or not call[1]["data"]


def test_push_knowledge_source_file_with_tags(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.pdf"
    doc.write_bytes(b"%PDF-1.4 fake pdf bytes")
    mock_client.post_multipart.return_value = {"_id": "task-2", "status": "queued"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
        "tags": ["demo", "sales"],
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    call = mock_client.post_multipart.call_args
    assert call[1]["data"] == {"tags": "demo,sales"}
    files = call[1]["files"]
    assert files["file"][2] == "application/pdf"


def test_push_knowledge_source_file_ctxt_extension(mock_client, state, cache, tmp_path):
    doc = tmp_path / "notes.ctxt"
    doc.write_text("chunked context text")
    mock_client.post_multipart.return_value = {"_id": "task-3", "status": "queued"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    files = mock_client.post_multipart.call_args[1]["files"]
    assert files["file"][2] == "text/plain"


def test_push_knowledge_source_file_unsupported_extension(mock_client, state, cache, tmp_path):
    doc = tmp_path / "spreadsheet.csv"
    doc.write_text("a,b,c")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "csv" in data["error"]
    mock_client.post_multipart.assert_not_called()


def test_push_knowledge_source_file_uppercase_extension(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.PDF"
    doc.write_bytes(b"%PDF-1.4 fake pdf bytes")
    mock_client.post_multipart.return_value = {"_id": "task-upper", "status": "queued"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    files = mock_client.post_multipart.call_args[1]["files"]
    assert files["file"][2] == "application/pdf"


def test_push_knowledge_source_file_zero_byte_file(mock_client, state, cache, tmp_path):
    doc = tmp_path / "empty.txt"
    doc.write_bytes(b"")
    mock_client.post_multipart.return_value = {"_id": "task-empty", "status": "queued"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["bytes"] == 0
    files = mock_client.post_multipart.call_args[1]["files"]
    assert files["file"][1] == b""


def test_push_knowledge_source_file_tag_with_comma_rejected(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.txt"
    doc.write_text("content")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
        "tags": ["a,b", "c"],
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "comma" in data["error"]
    mock_client.post_multipart.assert_not_called()


def test_push_knowledge_source_file_read_error_returns_error_not_raise(mock_client, state, cache, tmp_path, monkeypatch):
    doc = tmp_path / "policy.txt"
    doc.write_text("content")

    def _boom(self):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Permission denied" in data["error"]
    mock_client.post_multipart.assert_not_called()


def test_push_knowledge_source_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": "/nonexistent/policy.txt",
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post_multipart.assert_not_called()


def test_push_knowledge_source_file_api_failure(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.txt"
    doc.write_text("content")
    mock_client.post_multipart.side_effect = Exception("network error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({
        "file_path": str(doc),
        "knowledge_store_id": "ks-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "network error" in data["error"]


def test_push_knowledge_source_file_missing_knowledge_store_id_returns_validation_error(mock_client, state, cache, tmp_path):
    doc = tmp_path / "policy.txt"
    doc.write_text("content")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_knowledge_source_file"]({"file_path": str(doc)})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "knowledge_store_id" for d in data["details"])

