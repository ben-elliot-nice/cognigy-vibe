from __future__ import annotations
import base64
import difflib
import json
import struct
import time
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema

_KNOWLEDGE_SOURCE_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "ctxt": "text/plain",  # Cognigy's chunked-text source format; also plain text on the wire
}


class PushCodeNodeArgs(BaseModel):
    script_file: str = Field(description="Absolute path to .js or .ts file")
    flow_id: str
    node_id: str | None = Field(
        None,
        description="ID of an existing code node to update. Omit to create a new node.",
    )
    mode: str | None = Field(
        None,
        description="Required when creating: appendChild or append (see node-positioning)",
    )
    target: str | None = Field(
        None,
        description="Required when creating: ID of the reference node for positioning (see node-positioning)",
    )
    label: str | None = Field(None, description="Node label when creating (default: 'Code')")


class PushHtmlNodeArgs(BaseModel):
    html_file: str = Field(description="Absolute path to .html file")
    node_id: str
    flow_id: str


class PushAgentToolArgs(BaseModel):
    tool_file: str = Field(description="Absolute path to .tool.json file")
    flow_id: str
    node_id: str | None = Field(
        None,
        description="ID of an existing aiAgentJobTool node to update. Omit to create.",
    )
    job_node_id: str | None = Field(
        None,
        description="Required when creating: ID of the parent aiAgentJob node",
    )


class PushAgentAvatarArgs(BaseModel):
    image_file: str = Field(description="Absolute path to a 136×184px PNG file")
    agent_id: str = Field(description="Agent _id or referenceId")


class PushKnowledgeSourceFileArgs(BaseModel):
    file_path: str = Field(description="Absolute path to a .pdf, .txt, or .ctxt file")
    knowledge_store_id: str = Field(description="ID of the Knowledge Store to upload into")
    tags: list[str] | None = Field(
        None,
        description="Optional tags applied to the created Knowledge Source",
    )


class ExportPackageArgs(BaseModel):
    project_id: str = Field(description="Cognigy project _id to export")
    output_path: str = Field(
        description="Absolute or relative path where the zip file will be written",
    )
    name: str | None = Field(
        None,
        description="Package name. Defaults to the output filename without extension.",
    )
    resource_ids: list[str] | None = Field(
        None,
        description="Specific resource _ids to include. Defaults to all flows in the project.",
    )


_EXPORT_POLL_INTERVAL = 3.0   # seconds between job-status polls
_EXPORT_TIMEOUT = 300.0       # total seconds before giving up

TOOLS: list[Tool] = [
    Tool(
        name="push_code_node",
        description="Read a local .js/.ts file and push its content to a Cognigy Code node. "
                    "Two modes: "
                    "(1) UPDATE — provide node_id to push to an existing code node with conflict detection. "
                    "(2) CREATE — omit node_id and provide mode + target to create a new code node and push in one step. "
                    "Conflict detection: if the remote node was edited in the Cognigy UI since the last push, "
                    "the operation is blocked and a diff is returned.",
        inputSchema=make_schema(PushCodeNodeArgs),
    ),
    Tool(
        name="push_html_node",
        description="Read a local .html file and push it to a Cognigy setHTMLAppState node. "
                    "Automatically sets mode='full'.",
        inputSchema=make_schema(PushHtmlNodeArgs),
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
        inputSchema=make_schema(PushAgentToolArgs),
    ),
    Tool(
        name="push_agent_avatar",
        description=(
            "Read a local PNG file and push it as the avatar image on a Cognigy AI Agent. "
            "Validates PNG format and dimensions (must be exactly 136×184px). "
            "Encodes to base64 data URI and PATCHes the agent resource. "
            "See explain('agent-avatar-image') for the full avatar spec."
        ),
        inputSchema=make_schema(PushAgentAvatarArgs),
    ),
    Tool(
        name="push_knowledge_source_file",
        description=(
            "Upload a local .pdf/.txt/.ctxt file into a Cognigy Knowledge Store as a new "
            "Knowledge Source. Performs the real multipart/form-data upload — cognigy_invoke "
            "cannot do this (it only accepts JSON bodies). Ingestion runs asynchronously; the "
            "response is a Task (queued/active/done/error), not the finished Knowledge Source. "
            "The whole file is buffered into memory — fine for typical demo-build documents, "
            "avoid for very large files. "
            "See explain('knowledge-store') for the full ingestion workflow."
        ),
        inputSchema=make_schema(PushKnowledgeSourceFileArgs),
    ),
    Tool(
        name="export_package",
        description=(
            "Export a Cognigy project as a zip package and save it to a local file. "
            "Initiates an async export job via POST /v2.0/packages, polls until the job "
            "completes, then downloads the zip to the specified output path. "
            "Parent directories are created automatically. "
            "Typical output path: Demo Builds/<customer>-demo/<customer>-package.zip"
        ),
        inputSchema=make_schema(ExportPackageArgs),
    ),
]


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
        m, err = validate(PushCodeNodeArgs, args)
        if err:
            return err
        path = Path(m.script_file)
        node_id = m.node_id
        flow_id = m.flow_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        if not node_id:
            mode = m.mode
            target = m.target
            if not mode or not target:
                return _ok({"error": "Provide node_id to update an existing code node, or mode + target to create a new one"})
            body = {
                "type": "code",
                "label": m.label or "Code",
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
            label = m.label or "Code"
            cache.set("nodes", node_id, result)
            cache.set_node_snapshot(node_id, local_content)
            state.set("nodes", label, value={"id": node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": node_id, "created": True, "bytes": len(local_content)})

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
        m, err = validate(PushHtmlNodeArgs, args)
        if err:
            return err
        path = Path(m.html_file)
        node_id = m.node_id
        flow_id = m.flow_id

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
        m, err = validate(PushAgentToolArgs, args)
        if err:
            return err
        path = Path(m.tool_file)
        node_id = m.node_id
        flow_id = m.flow_id

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
            job_node_id = m.job_node_id
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
        m, err = validate(PushAgentAvatarArgs, args)
        if err:
            return err
        path = Path(m.image_file)
        agent_id = m.agent_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        data = path.read_bytes()

        if len(data) < 24:
            return _ok({"error": f"File is too small to be a valid PNG: {path.name}"})

        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return _ok({"error": f"File is not a PNG (wrong magic bytes): {path.name}"})

        if data[12:16] != b'IHDR':
            return _ok({"error": f"File is not a valid PNG (missing IHDR chunk): {path.name}"})

        w = struct.unpack('>I', data[16:20])[0]
        h = struct.unpack('>I', data[20:24])[0]

        if w != 136 or h != 184:
            ratio = w / h if h else 0
            target_ratio = 136 / 184
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

    def _push_knowledge_source_file(args: dict) -> list[TextContent]:
        m, err = validate(PushKnowledgeSourceFileArgs, args)
        if err:
            return err
        path = Path(m.file_path)

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        ext = path.suffix.lstrip(".").lower()
        content_type = _KNOWLEDGE_SOURCE_CONTENT_TYPES.get(ext)
        if content_type is None:
            supported = ', '.join('.' + e for e in _KNOWLEDGE_SOURCE_CONTENT_TYPES)
            found = f".{ext}" if ext else "no file extension"
            return _ok({"error": f"Unsupported file type: {found}. Supported formats: {supported}"})

        if m.tags:
            if any("," in tag for tag in m.tags):
                return _ok({"error": "Tags must not contain commas (the API joins tags with a comma delimiter)"})
            if any(not tag for tag in m.tags):
                return _ok({"error": "Tags must not be empty strings"})

        try:
            data = path.read_bytes()
        except OSError as e:
            return _ok({"error": f"Failed to read file: {e}"})

        files = {"file": (path.name, data, content_type)}
        form_data = {"tags": ",".join(m.tags)} if m.tags else None

        try:
            result = client.post_multipart(
                f"/v2.0/knowledgestores/{m.knowledge_store_id}/sources/upload",
                files=files,
                data=form_data,
            )
        except Exception as e:
            return _ok({"error": f"Failed to upload knowledge source file: {e}"})

        if not isinstance(result, dict):
            return _ok({"error": f"Unexpected response from upload endpoint: {result!r}"})

        if result.get("status") == "error":
            return _ok({
                "error": f"Upload task failed: {result.get('failReason', 'unknown error')}",
                "task_id": result.get("_id"),
            })

        task_id = result.get("_id")
        if not task_id:
            return _ok({"error": f"Upload response missing _id: {result}"})

        return _ok({
            "success": True,
            "task_id": task_id,
            "status": result.get("status"),
            "bytes": len(data),
        })

    def _export_package(args: dict) -> list[TextContent]:
        m, err = validate(ExportPackageArgs, args)
        if err:
            return err
        project_id = m.project_id
        output_path = Path(m.output_path)
        package_name = m.name or output_path.stem

        # Resolve resourceIds — required by the API.
        # If not supplied, fetch all flows for the project and use their _ids.
        if m.resource_ids is not None:
            resource_ids = m.resource_ids
        else:
            try:
                flows_resp = client.get("/v2.0/flows", projectId=project_id, limit=100)
                resource_ids = [f["_id"] for f in flows_resp.get("items", []) if "_id" in f]
            except Exception as e:
                return _ok({"error": f"Failed to fetch flows to populate resourceIds: {e}"})
            if not resource_ids:
                return _ok({"error": "No flows found for project — cannot create an empty package"})

        # Kick off the async export job — returns a Task object, not a Package.
        # The _id in the response is the task ID, not the package ID.
        try:
            job = client.post("/v2.0/packages", {
                "projectId": project_id,
                "name": package_name,
                "resourceIds": resource_ids,
            })
        except Exception as e:
            return _ok({"error": f"Failed to start export job: {e}"})

        task_id = job.get("_id")
        if not task_id:
            return _ok({"error": f"Export job response missing _id: {job}"})

        # Poll GET /v2.0/tasks/{taskId} until the task reaches a terminal status.
        # Terminal statuses: done, error, cancelled, cancelling.
        # (GET /v2.0/packages/{id} returns a Package object with no status field —
        # it cannot be used for polling.)
        deadline = time.monotonic() + _EXPORT_TIMEOUT
        while True:
            if time.monotonic() > deadline:
                return _ok({
                    "error": f"Export task {task_id} timed out after {_EXPORT_TIMEOUT:.0f}s",
                    "task_id": task_id,
                })
            time.sleep(_EXPORT_POLL_INTERVAL)
            try:
                task = client.get(f"/v2.0/tasks/{task_id}")
            except Exception as e:
                return _ok({"error": f"Failed to poll export task {task_id}: {e}", "task_id": task_id})

            task_status = task.get("status", "")
            if task_status == "error":
                return _ok({
                    "error": f"Export task failed: {task.get('failReason', 'unknown error')}",
                    "task_id": task_id,
                })
            if task_status in ("cancelled", "cancelling"):
                return _ok({
                    "error": f"Export task was cancelled (status: {task_status})",
                    "task_id": task_id,
                })
            if task_status == "done":
                break
            # queued or active — keep polling

        # Resolve the package ID: the task _id is not the package _id.
        # List packages for this project sorted by creation time descending and
        # take the first result — that is the package the completed task just created.
        try:
            packages = client.get(
                "/v2.0/packages",
                projectId=project_id,
                sort="createdAt:desc",
                limit=1,
            )
        except Exception as e:
            return _ok({"error": f"Failed to list packages after export: {e}", "task_id": task_id})

        items = packages.get("items", [])
        if not items:
            return _ok({"error": "No packages found for project after export completed", "task_id": task_id})
        package_id = items[0].get("_id")
        if not package_id:
            return _ok({"error": f"Package listing returned item without _id: {items[0]}", "task_id": task_id})

        # Obtain a pre-signed download URL via POST /v2.0/packages/{packageId}/downloadlink.
        # The response contains {downloadLink: <uri>} — the zip must be fetched from that URI
        # directly, not via the Cognigy API base path.
        try:
            link_resp = client.post(f"/v2.0/packages/{package_id}/downloadlink", {})
        except Exception as e:
            return _ok({"error": f"Failed to get download link for package {package_id}: {e}", "task_id": task_id})

        download_link = link_resp.get("downloadLink")
        if not download_link:
            return _ok({"error": f"downloadlink response missing downloadLink field: {link_resp}", "task_id": task_id})

        try:
            zip_bytes = client.download_url(download_link)
        except Exception as e:
            return _ok({"error": f"Failed to download package zip from pre-signed URL: {e}", "task_id": task_id})

        # Write to disk, creating parent dirs as needed
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(zip_bytes)
        except OSError as e:
            return _ok({"error": f"Failed to write zip to {output_path}: {e}", "task_id": task_id})

        return _ok({
            "success": True,
            "task_id": task_id,
            "package_id": package_id,
            "output_path": str(output_path),
            "bytes": len(zip_bytes),
        })

    return {
        "push_code_node": _push_code_node,
        "push_html_node": _push_html_node,
        "push_agent_tool": _push_agent_tool,
        "push_agent_avatar": _push_agent_avatar,
        "push_knowledge_source_file": _push_knowledge_source_file,
        "export_package": _export_package,
    }
