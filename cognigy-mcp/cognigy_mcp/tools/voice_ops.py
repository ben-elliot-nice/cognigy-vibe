from __future__ import annotations
import json
import os
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class ProvisionWebrtcEndpointArgs(BaseModel):
    project_id: str
    flow_id: str = Field(description="Hex _id of the flow to bind")
    flow_reference_id: str = Field(description="UUID referenceId of the flow")
    endpoint_name: str = Field(description="Name for the webRTC endpoint, e.g. 'Click-to-Call'")
    connection_name: str = Field(description="Name for the speech connection, e.g. 'Test'")
    region: str = Field("australiaeast", description="Azure Speech region, e.g. 'australiaeast'")

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
        inputSchema=make_schema(ProvisionWebrtcEndpointArgs),
    )
]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:
    def _provision_webrtc_endpoint(args: dict) -> list[TextContent]:
        m, err = validate(ProvisionWebrtcEndpointArgs, args)
        if err:
            return err
        endpoint_base = client.endpoint_base_url
        api_key = os.environ.get("COGNIGY_VOICE_PREVIEW_API_KEY")
        is_dummy = not bool(api_key)
        effective_key = api_key if api_key else "dummy"

        conn_result = client.post("/v2.0/connections", {
            "name": m.connection_name,
            "extension": "@cognigy/audio-preview-provider",
            "type": "MicrosoftSpeechProvider",
            "resourceLevel": "project",
            "projectId": m.project_id,
            "fields": {"apiKey": effective_key, "region": m.region},
        })
        connection_id = conn_result["_id"]

        try:
            ep_result = client.post("/v2.0/endpoints", {
                "name": m.endpoint_name,
                "channel": "voiceGateway2",
                "flowId": m.flow_id,
                "flowReferenceId": m.flow_reference_id,
                "projectId": m.project_id,
                "webrtcWidgetConfig": {"active": True},
            })
        except Exception:
            try:
                client.delete(f"/v2.0/connections/{connection_id}")
            except Exception:
                pass
            raise

        endpoint_id = ep_result["_id"]
        url_token = ep_result.get("URLToken") or ep_result.get("urlToken", "")
        demo_url = f"{endpoint_base}/demo/{url_token}"

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
