from __future__ import annotations
import difflib
import json
from pathlib import Path
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="push_code_node",
        description="Read a local .js/.ts file and push its content to a Cognigy Code node. "
                    "Performs conflict detection: if the remote node was edited in the Cognigy UI "
                    "since the last push, the operation is blocked and a diff is returned.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_file": {"type": "string", "description": "Absolute path to .js or .ts file"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["script_file", "node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_html_node",
        description="Read a local .html file and push it to a Cognigy setHTMLAppState node. "
                    "Automatically sets mode='full'.",
        inputSchema={
            "type": "object",
            "properties": {
                "html_file": {"type": "string", "description": "Absolute path to .html file"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["html_file", "node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_tool_from_file",
        description="Read a local JSON tool definition and create or update it in Cognigy.",
        inputSchema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Absolute path to JSON tool definition"},
                "project_id": {"type": "string"},
                "tool_id": {"type": "string", "description": "If provided, updates existing tool instead of creating"},
            },
            "required": ["file", "project_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _diff_summary(old: str, new: str) -> str:
    lines = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="last-pushed",
        tofile="remote-current",
        n=3,
    ))
    if len(lines) > 50:
        truncated = lines[:50]
        truncated.append(f"\n... ({len(lines) - 50} more lines not shown)\n")
        return "".join(truncated)
    return "".join(lines)


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _push_code_node(args: dict) -> list[TextContent]:
        path = Path(args["script_file"])
        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        try:
            remote = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}")
        except Exception as e:
            return _ok({"error": f"Failed to fetch remote node: {e}"})

        remote_code = remote.get("config", {}).get("code", "")
        snapshot = cache.get_node_snapshot(node_id)

        # Conflict: remote has been edited in UI since last push
        if snapshot is not None and remote_code != snapshot:
            return _ok({
                "conflict": True,
                "message": "Remote node was edited in the Cognigy UI since the last push. "
                           "Review the diff and decide whether to overwrite or incorporate the changes.",
                "diff": _diff_summary(snapshot, remote_code),
            })

        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"code": local_content}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to push code to node: {e}"})
        cache.set("nodes", node_id, result)
        cache.set_node_snapshot(node_id, local_content)
        return _ok({"success": True, "node_id": node_id, "bytes": len(local_content)})

    def _push_html_node(args: dict) -> list[TextContent]:
        path = Path(args["html_file"])
        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        html = path.read_text()
        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"html": html, "mode": "full"}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to patch node: {e}"})
        cache.set("nodes", node_id, result)
        return _ok({"success": True, "node_id": node_id, "bytes": len(html)})

    def _push_tool_from_file(args: dict) -> list[TextContent]:
        path = Path(args["file"])
        project_id = args["project_id"]
        tool_id = args.get("tool_id")

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        try:
            body = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return _ok({"error": f"Invalid JSON in {path}: {e}"})

        try:
            if tool_id:
                result = client.patch(f"/v2.0/projects/{project_id}/tools/{tool_id}", body)
            else:
                result = client.post(f"/v2.0/projects/{project_id}/tools", body)
        except Exception as e:
            return _ok({"error": f"Failed to push tool: {e}"})

        name = result.get("name")
        rid = result.get("_id")
        if name and rid:
            state.set("tools", name, value={"id": rid})
        return _ok(result)

    return {
        "push_code_node": _push_code_node,
        "push_html_node": _push_html_node,
        "push_tool_from_file": _push_tool_from_file,
    }
