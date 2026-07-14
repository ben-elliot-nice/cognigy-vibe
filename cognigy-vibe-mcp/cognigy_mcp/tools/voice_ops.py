from __future__ import annotations
import os
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class ProvisionWebrtcEndpointArgs(BaseModel):
    project_id: str
    flow_reference_id: str = Field(description="UUID referenceId of the flow to bind")
    endpoint_name: str = Field(description="Name for the webRTC endpoint, e.g. 'Click-to-Call'")
    connection_name: str = Field(description="Name for the speech connection, e.g. 'Test'")
    connection_type: str = Field(
        "MicrosoftSpeechProvider",
        description="Cognigy connection type for the preview speech provider",
    )
    connection_fields: dict = Field(
        default_factory=lambda: {"region": "australiaeast"},
        description="Non-credential connection fields for the preview speech provider (vendor-specific shape)",
    )

TOOLS: list[Tool] = [
    Tool(
        name="provision_webrtc_endpoint",
        description=(
            "Create a VoiceGateway webRTC (Click-to-Call) endpoint bound to a flow. "
            "Handles the Microsoft Azure Speech Services connection prerequisite "
            "automatically: uses COGNIGY_VOICE_PREVIEW_API_KEY from environment for "
            "a real connection, or creates and deletes a throwaway dummy connection "
            "when the key is absent. Also wires the connection into the project's "
            "audioPreviewSettings and fetches the project's primary locale — both "
            "required by the live API for voiceGateway2 endpoints. "
            "Returns endpoint_id, url_token, demo_url, connection_id (null if dummy), "
            "and path ('real' or 'dummy'). "
            "Demo calls work on both paths; the in-browser voice-preview widget only "
            "works when real credentials are configured."
        ),
        inputSchema=make_schema(ProvisionWebrtcEndpointArgs),
    )
]

_WEBRTC_WIDGET_CONFIG = {
    "label": "",
    "active": True,
    "theme": "DARK_MODE",
    "transcription": {"enabled": True, "backgroundMode": "transparent"},
    "demoPage": {"background": {"mode": "color", "color": "#FFFFFF"}, "position": "centered"},
}


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
            "type": m.connection_type,
            "resourceLevel": "project",
            "projectId": m.project_id,
            "fields": {"apiKey": effective_key, **m.connection_fields},
        }, retry=False)
        connection_id = conn_result["_id"]

        endpoint_id = None
        try:
            connection_reference_id = conn_result["referenceId"]
            client.patch(f"/v2.0/projects/{m.project_id}/settings", {
                "audioPreviewSettings": {
                    "provider": "microsoft",
                    "connections": {"microsoft": {"connectionId": connection_reference_id}},
                }
            })

            locales = client.get("/v2.0/locales", projectId=m.project_id)
            locale_items = locales.get("items", [])
            if not locale_items:
                raise ValueError(f"Project {m.project_id} has no locales configured")
            locale = next((loc for loc in locale_items if loc.get("primary")), locale_items[0])
            locale_reference_id = locale["referenceId"]

            ep_result = client.post("/v2.0/endpoints", {
                "projectId": m.project_id,
                "entrypoint": m.project_id,
                "name": m.endpoint_name,
                "channel": "voiceGateway2",
                "localeId": locale_reference_id,
                "flowId": m.flow_reference_id,
                "agentId": "",
                "targetType": "flow",
                "customIcon": "",
            }, retry=False)
            endpoint_id = ep_result["_id"]
            url_token = ep_result.get("URLToken") or ep_result.get("urlToken", "")

            client.patch(f"/v2.0/endpoints/{endpoint_id}", {
                "createWebrtcClient": True,
                "channel": "voiceGateway2",
                "name": m.endpoint_name,
                "URLToken": url_token,
                "localeId": locale_reference_id,
                "webrtcWidgetConfig": _WEBRTC_WIDGET_CONFIG,
            })
        except Exception:
            if endpoint_id:
                try:
                    client.delete(f"/v2.0/endpoints/{endpoint_id}")
                except Exception:
                    pass
            try:
                client.delete(f"/v2.0/connections/{connection_id}")
            except Exception:
                pass
            raise

        demo_url = f"{endpoint_base}/demo/{url_token}"

        state.set("endpoints", m.endpoint_name, value={
            "id": endpoint_id,
            "urlToken": url_token,
            "flowReferenceId": m.flow_reference_id,
        })
        cache.set("endpoints", endpoint_id, ep_result)

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
