from __future__ import annotations
import json
import os
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="provision_webrtc_endpoint",
        description=(
            "Create a VoiceGateway webRTC (Click-to-Call) endpoint bound to a flow. "
            "Handles the Microsoft Azure Speech Services connection prerequisite "
            "automatically: uses COGNIGY_VOICE_PREVIEW_API_KEY from environment for "
            "a real connection, or creates and deletes a throwaway dummy connection "
            "when the key is absent. "
            "Returns endpoint_id, url_token, demo_url, connection_id (null if dummy), "
            "and path ('real' or 'dummy'). "
            "Demo calls work on both paths; the in-browser voice-preview widget only "
            "works when real credentials are configured."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "flow_id": {
                    "type": "string",
                    "description": "Hex _id of the flow to bind",
                },
                "flow_reference_id": {
                    "type": "string",
                    "description": "UUID referenceId of the flow",
                },
                "endpoint_name": {
                    "type": "string",
                    "description": "Name for the webRTC endpoint, e.g. 'Click-to-Call'",
                },
                "connection_name": {
                    "type": "string",
                    "description": "Name for the speech connection, e.g. 'Test'",
                },
                "region": {
                    "type": "string",
                    "description": "Azure Speech region, e.g. 'australiaeast'",
                    "default": "australiaeast",
                },
            },
            "required": [
                "project_id",
                "flow_id",
                "flow_reference_id",
                "endpoint_name",
                "connection_name",
            ],
        },
    )
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:
    def _provision_webrtc_endpoint(args: dict) -> list[TextContent]:
        project_id = args["project_id"]
        flow_id = args["flow_id"]
        flow_reference_id = args["flow_reference_id"]
        endpoint_name = args["endpoint_name"]
        connection_name = args["connection_name"]
        region = args.get("region", "australiaeast")

        api_key = os.environ.get("COGNIGY_VOICE_PREVIEW_API_KEY")
        is_dummy = not bool(api_key)
        effective_key = api_key if api_key else "dummy"

        # Create speech connection — required prerequisite for webRTC endpoint creation
        conn_result = client.post("/v2.0/connections", {
            "name": connection_name,
            "extension": "@cognigy/audio-preview-provider",
            "type": "MicrosoftSpeechProvider",
            "resourceLevel": "project",
            "projectId": project_id,
            "fields": {"apiKey": effective_key, "region": region},
        })
        connection_id = conn_result["_id"]

        # Create webRTC endpoint bound to the flow
        ep_result = client.post("/v2.0/endpoints", {
            "name": endpoint_name,
            "channel": "voiceGateway2",
            "flowId": flow_id,
            "flowReferenceId": flow_reference_id,
            "projectId": project_id,
            "webrtcWidgetConfig": {"active": True},
        })
        endpoint_id = ep_result["_id"]
        url_token = ep_result.get("URLToken") or ep_result.get("urlToken", "")

        try:
            demo_url = f"{client.endpoint_base_url}/demo/{url_token}"
        except ValueError:
            demo_url = f"/demo/{url_token}"

        # Dummy path: remove the throwaway connection
        if is_dummy:
            client.delete(f"/v2.0/connections/{connection_id}")
            connection_id = None

        return _ok({
            "endpoint_id": endpoint_id,
            "url_token": url_token,
            "demo_url": demo_url,
            "connection_id": connection_id,
            "path": "dummy" if is_dummy else "real",
        })

    return {"provision_webrtc_endpoint": _provision_webrtc_endpoint}
