from __future__ import annotations
import base64
import difflib
import json
import struct
from pathlib import Path
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="push_code_node",
        description="Read a local .js/.ts file and push its content to a Cognigy Code node. "
                    "Two modes: "
                    "(1) UPDATE — provide node_id to push to an existing code node with conflict detection. "
                    "(2) CREATE — omit node_id and provide mode + target to create a new code node and push in one step. "
                    "Conflict detection: if the remote node was edited in the Cognigy UI since the last push, "
                    "the operation is blocked and a diff is returned.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_file": {"type": "string", "description": "Absolute path to .js or .ts file"},
                "flow_id": {"type": "string"},
                "node_id": {"type": "string", "description": "ID of an existing code node to update. Omit to create a new node."},
                "mode": {"type": "string", "description": "Required when creating: appendChild or append (see node-positioning)"},
                "target": {"type": "string", "description": "Required when creating: ID of the reference node for positioning"},
                "label": {"type": "string", "description": "Node label when creating (default: 'Code')"},
            },
            "required": ["script_file", "flow_id"],
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
        name="push_agent_tool",
        description=(
            "Read a local .tool.json file and push its definition to a Cognigy aiAgentJobTool node. "
            "Two modes: "
            "(1) UPDATE — provide node_id to update an existing aiAgentJobTool node. "
            "(2) CREATE — omit node_id and provide job_node_id to create a new tool node as a child of an aiAgentJob node. "
            "The .tool.json file must contain toolId and description. "
            "parameters (JSON Schema object) and condition (CognigyScript) are optional. "
            "See explain('agent-tool-json') for the .tool.json file convention."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tool_file": {"type": "string", "description": "Absolute path to .tool.json file"},
                "flow_id": {"type": "string"},
                "node_id": {"type": "string", "description": "ID of an existing aiAgentJobTool node to update. Omit to create."},
                "job_node_id": {"type": "string", "description": "Required when creating: ID of the parent aiAgentJob node"},
            },
            "required": ["tool_file", "flow_id"],
        },
    ),
    Tool(
        name="push_agent_avatar",
        description=(
            "Read a local PNG file and push it as the avatar image on a Cognigy AI Agent. "
            "Validates PNG format and dimensions (must be exactly 136×184px). "
            "Encodes to base64 data URI and PATCHes the agent resource. "
            "See explain('agent-avatar-image') for the full avatar spec."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "image_file": {"type": "string", "description": "Absolute path to a 136×184px PNG file"},
                "agent_id": {"type": "string", "description": "Agent _id or referenceId"},
            },
            "required": ["image_file", "agent_id"],
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
        node_id = args.get("node_id")
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        # Creation path: no node_id provided — create then push
        if not node_id:
            mode = args.get("mode")
            target = args.get("target")
            if not mode or not target:
                return _ok({"error": "Provide node_id to update an existing code node, or mode + target to create a new one"})
            body = {
                "type": "code",
                "label": args.get("label", "Code"),
                "mode": mode,
                "target": target,
                "extension": "@cognigy/basic-nodes",
                "config": {"code": local_content},
            }
            try:
                result = client.post(f"/v2.0/flows/{flow_id}/chart/nodes", body)
            except Exception as e:
                return _ok({"error": f"Failed to create code node: {e}"})
            node_id = result["_id"]
            label = args.get("label", "Code")
            cache.set("nodes", node_id, result)
            cache.set_node_snapshot(node_id, local_content)
            state.set("nodes", label, value={"id": node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": node_id, "created": True, "bytes": len(local_content)})

        # Update path: push to existing node with conflict detection
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

    def _push_agent_tool(args: dict) -> list[TextContent]:
        path = Path(args["tool_file"])
        node_id = args.get("node_id")
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        try:
            tool_spec = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return _ok({"error": f"Invalid JSON in {path}: {e}"})

        if not isinstance(tool_spec, dict):
            return _ok({"error": f"tool.json must be a JSON object, got {type(tool_spec).__name__}"})

        missing = [f for f in ("toolId", "description") if not tool_spec.get(f)]
        if missing:
            return _ok({"error": f"Missing required fields in tool file: {', '.join(missing)}"})

        parameters = tool_spec.get("parameters")
        use_parameters = parameters is not None

        config: dict = {
            "toolId": tool_spec["toolId"],
            "description": tool_spec["description"],
            "useParameters": use_parameters,
            "debugMessage": True,
            "condition": tool_spec.get("condition", ""),
        }
        if use_parameters:
            config["parameters"] = json.dumps(parameters, separators=(",", ":"))

        if not node_id:
            job_node_id = args.get("job_node_id")
            if not job_node_id:
                return _ok({"error": "Provide node_id to update an existing tool node, or job_node_id to create a new one"})
            body = {
                "type": "aiAgentJobTool",
                "extension": "@cognigy/basic-nodes",
                "label": tool_spec.get("label", tool_spec["toolId"]),
                "mode": "appendChild",
                "target": job_node_id,
                "config": config,
            }
            try:
                result = client.post(f"/v2.0/flows/{flow_id}/chart/nodes", body)
            except Exception as e:
                return _ok({"error": f"Failed to create tool node: {e}"})
            new_node_id = result["_id"]
            state.set("nodes", tool_spec["toolId"], value={"id": new_node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": new_node_id, "created": True})

        try:
            client.patch(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}", {"config": config})
        except Exception as e:
            return _ok({"error": f"Failed to update tool node: {e}"})
        return _ok({"success": True, "node_id": node_id, "updated": True})

    def _push_agent_avatar(args: dict) -> list[TextContent]:
        path = Path(args["image_file"])
        agent_id = args["agent_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        data = path.read_bytes()

        if data[:4] != b'\x89PNG':
            return _ok({"error": f"File is not a PNG (wrong magic bytes): {path.name}"})

        w = struct.unpack('>I', data[16:20])[0]
        h = struct.unpack('>I', data[20:24])[0]

        if w != 136 or h != 184:
            ratio = w / h if h else 0
            target_ratio = 136 / 184  # ≈ 0.7391
            if abs(ratio - target_ratio) <= 0.01:
                return _ok({"error": f"Image is {w}×{h}px. Correct ratio — resize to 136×184 and re-run."})
            return _ok({"error": f"Image is {w}×{h}px. Expected 136×184px."})

        data_uri = "data:image/png;base64," + base64.b64encode(data).decode()
        try:
            client.patch(f"/v2.0/aiagents/{agent_id}", {
                "image": data_uri,
                "imageOptimizedFormat": True,
            })
        except Exception as e:
            return _ok({"error": f"Failed to update agent avatar: {e}"})

        return _ok({"success": True, "agent_id": agent_id, "bytes": len(data)})

    return {
        "push_code_node": _push_code_node,
        "push_html_node": _push_html_node,
        "push_agent_tool": _push_agent_tool,
        "push_agent_avatar": _push_agent_avatar,
    }
