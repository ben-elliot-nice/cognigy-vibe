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
        description="Push a .js/.ts file to a Cognigy Code node. "
                    "Local mode: provide script_file (absolute path). "
                    "Remote mode: provide workspace_file (relative path within session workspace). "
                    "Performs conflict detection against the last-pushed snapshot.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_file": {"type": "string", "description": "Absolute path to .js or .ts file (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_html_node",
        description="Push a .html file to a Cognigy setHTMLAppState node. "
                    "Local mode: provide html_file (absolute path). "
                    "Remote mode: provide workspace_file (relative path). "
                    "Automatically sets mode='full'.",
        inputSchema={
            "type": "object",
            "properties": {
                "html_file": {"type": "string", "description": "Absolute path to .html file (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_tool_from_file",
        description="Read a local JSON tool definition and create or update it in Cognigy. "
                    "Local mode: provide file (absolute path). "
                    "Remote mode: provide workspace_file (relative path).",
        inputSchema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Absolute path to JSON tool definition (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "project_id": {"type": "string"},
                "tool_id": {"type": "string", "description": "If provided, updates existing tool instead of creating"},
            },
            "required": ["project_id"],
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


def _resolve_path(args: dict, local_key: str, workspace_dir: Path | None) -> tuple[Path | None, list[TextContent] | None]:
    """Resolve script_file/html_file/file or workspace_file to an absolute Path.

    Returns (path, None) on success, or (None, error_response) on failure.
    """
    workspace_file = args.get("workspace_file")
    local_file = args.get(local_key)

    if workspace_file and local_file:
        return None, _ok({"error": f"Provide either {local_key} or workspace_file, not both"})

    if workspace_file:
        if workspace_dir is None:
            return None, _ok({"error": "workspace_file is only supported in remote (HTTP) server mode"})
        return workspace_dir / workspace_file, None

    if local_file:
        return Path(local_file), None

    return None, _ok({"error": f"Either {local_key} or workspace_file is required"})


def make_handlers(
    client: CognigyClient,
    state: ProjectState,
    cache: Cache,
    workspace_dir: Path | None = None,
) -> dict:

    def _push_code_node(args: dict) -> list[TextContent]:
        path, err = _resolve_path(args, "script_file", workspace_dir)
        if err:
            return err

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
        path, err = _resolve_path(args, "html_file", workspace_dir)
        if err:
            return err

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
        path, err = _resolve_path(args, "file", workspace_dir)
        if err:
            return err

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
