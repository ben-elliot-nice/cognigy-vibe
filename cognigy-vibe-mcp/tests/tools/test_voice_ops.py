import json
import pytest
from unittest.mock import PropertyMock
from cognigy_mcp.api import ApiError
from cognigy_mcp.tools.voice_ops import make_handlers, TOOLS


LOCALES_RESPONSE = {
    "items": [
        {"_id": "loc-hex-1", "referenceId": "locale-uuid-1", "name": "en-AU", "primary": True},
    ]
}

WIDGET_CONFIG = {
    "label": "",
    "active": True,
    "theme": "DARK_MODE",
    "transcription": {"enabled": True, "backgroundMode": "transparent"},
    "demoPage": {"background": {"mode": "color", "color": "#FFFFFF"}, "position": "centered"},
}


def _args(mock_client, connection_result=None, endpoint_result=None, patch_settings_result=None,
          patch_widget_result=None):
    mock_client.get.return_value = LOCALES_RESPONSE
    mock_client.post.side_effect = [
        connection_result or {"_id": "conn-1", "referenceId": "conn-ref-1"},
        endpoint_result or {"_id": "ep-1", "URLToken": "tok123"},
    ]
    mock_client.patch.side_effect = [
        patch_settings_result if patch_settings_result is not None else {},
        patch_widget_result if patch_widget_result is not None else {},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"


def test_tool_exported():
    names = [t.name for t in TOOLS]
    assert "provision_webrtc_endpoint" in names


def test_real_creds_path(mock_client, state, cache, monkeypatch):
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    data = json.loads(result[0].text)

    assert data["path"] == "real"
    assert data["endpoint_id"] == "ep-1"
    assert data["url_token"] == "tok123"
    assert data["demo_url"] == "https://cognigy-endpoint-au1.nicecxone.com/demo/tok123"
    assert data["connection_id"] == "conn-1"
    mock_client.delete.assert_not_called()


def test_dummy_path_deletes_connection(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client, connection_result={"_id": "conn-dummy", "referenceId": "conn-dummy-ref"},
          endpoint_result={"_id": "ep-2", "URLToken": "tok456"})

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    data = json.loads(result[0].text)

    assert data["path"] == "dummy"
    assert data["connection_id"] is None
    assert data["endpoint_id"] == "ep-2"
    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-dummy")


def test_dummy_path_sends_dummy_api_key(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "connection_fields": {"region": "australiaeast"},
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["fields"]["apiKey"] == "dummy"
    assert conn_body["fields"]["region"] == "australiaeast"


def test_real_creds_path_sends_real_api_key(mock_client, state, cache, monkeypatch):
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "my-real-key")
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "connection_fields": {"region": "australiaeast"},
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["fields"]["apiKey"] == "my-real-key"


def test_connection_post_body(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "MyConn",
        "connection_fields": {"region": "eastus"},
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["name"] == "MyConn"
    assert conn_body["extension"] == "@cognigy/audio-preview-provider"
    assert conn_body["type"] == "MicrosoftSpeechProvider"
    assert conn_body["resourceLevel"] == "project"
    assert conn_body["projectId"] == "proj-abc"
    assert conn_body["fields"]["region"] == "eastus"


def test_audio_preview_settings_patch_uses_connection_reference_id(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client, connection_result={"_id": "conn-1", "referenceId": "conn-ref-xyz"})

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    settings_path, settings_body = mock_client.patch.call_args_list[0][0]
    assert settings_path == "/v2.0/projects/proj-abc/settings"
    assert settings_body == {
        "audioPreviewSettings": {
            "provider": "microsoft",
            "connections": {"microsoft": {"connectionId": "conn-ref-xyz"}},
        }
    }


def test_locales_fetched_and_primary_locale_used(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    mock_client.get.return_value = {
        "items": [
            {"_id": "loc-a", "referenceId": "ref-a", "name": "de-DE", "primary": False},
            {"_id": "loc-b", "referenceId": "ref-b", "name": "en-AU", "primary": True},
        ]
    }
    mock_client.post.side_effect = [
        {"_id": "conn-1", "referenceId": "conn-ref-1"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.patch.side_effect = [{}, {}]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    mock_client.get.assert_called_once_with("/v2.0/locales", projectId="proj-abc")
    ep_body = mock_client.post.call_args_list[1][0][1]
    assert ep_body["localeId"] == "ref-b"


def test_endpoint_post_body(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_reference_id": "fref-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    ep_body = mock_client.post.call_args_list[1][0][1]
    assert ep_body["channel"] == "voiceGateway2"
    assert ep_body["flowId"] == "fref-uuid"
    assert "flowReferenceId" not in ep_body
    assert ep_body["projectId"] == "proj-abc"
    assert ep_body["entrypoint"] == "proj-abc"
    assert ep_body["localeId"] == "locale-uuid-1"
    assert ep_body["agentId"] == ""
    assert ep_body["targetType"] == "flow"
    assert ep_body["customIcon"] == ""
    assert ep_body["name"] == "Click-to-Call"
    assert "webrtcWidgetConfig" not in ep_body


def test_widget_enable_patch_body(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client, endpoint_result={"_id": "ep-1", "URLToken": "tok123"})

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_reference_id": "fref-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    widget_path, widget_body = mock_client.patch.call_args_list[1][0]
    assert widget_path == "/v2.0/endpoints/ep-1"
    assert widget_body == {
        "createWebrtcClient": True,
        "channel": "voiceGateway2",
        "name": "Click-to-Call",
        "URLToken": "tok123",
        "localeId": "locale-uuid-1",
        "webrtcWidgetConfig": WIDGET_CONFIG,
    }


def test_urltoken_lowercase_fallback(mock_client, state, cache, monkeypatch):
    """Handles lowercase urlToken returned by some environments."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client, endpoint_result={"_id": "ep-1", "urlToken": "lower-tok"})

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "p", "flow_reference_id": "r",
        "endpoint_name": "Click-to-Call", "connection_name": "Test",
    })
    data = json.loads(result[0].text)
    assert data["url_token"] == "lower-tok"
    assert "lower-tok" in data["demo_url"]

    widget_path, widget_body = mock_client.patch.call_args_list[1][0]
    assert widget_body["URLToken"] == "lower-tok"


def test_endpoint_base_url_raises_propagates_before_api_calls(mock_client, state, cache, monkeypatch):
    """ValueError from endpoint_base_url raises immediately — no API calls made."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    type(mock_client).endpoint_base_url = PropertyMock(side_effect=ValueError("no cognigy-api- in URL"))

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ValueError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "p", "flow_reference_id": "r",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.post.assert_not_called()
    mock_client.patch.assert_not_called()
    mock_client.delete.assert_not_called()


def test_locale_fetch_failure_cleans_up_connection(mock_client, state, cache, monkeypatch):
    """If the locales GET raises, the speech connection is deleted before re-raising."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.post.side_effect = [{"_id": "conn-real", "referenceId": "conn-ref-real"}]
    mock_client.patch.side_effect = [{}]
    mock_client.get.side_effect = ApiError(500, "locales fetch failed")

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ApiError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-real")


def test_endpoint_post_failure_cleans_up_connection(mock_client, state, cache, monkeypatch):
    """If the endpoint creation POST raises, the speech connection is deleted before re-raising."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.get.return_value = LOCALES_RESPONSE
    mock_client.patch.side_effect = [{}]
    mock_client.post.side_effect = [
        {"_id": "conn-real", "referenceId": "conn-ref-real"},
        ApiError(500, "endpoint creation failed"),
    ]

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ApiError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-real")


def test_widget_patch_failure_cleans_up_connection_and_endpoint(mock_client, state, cache, monkeypatch):
    """If the widget-enable PATCH raises after the endpoint was already created,
    both the orphaned endpoint and the speech connection are deleted before re-raising."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.get.return_value = LOCALES_RESPONSE
    mock_client.post.side_effect = [
        {"_id": "conn-real", "referenceId": "conn-ref-real"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.patch.side_effect = [{}, ApiError(400, "widget enable failed")]

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ApiError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    assert mock_client.delete.call_args_list == [
        (("/v2.0/endpoints/ep-1",),),
        (("/v2.0/connections/conn-real",),),
    ]


def test_connection_reference_id_missing_cleans_up_connection(mock_client, state, cache, monkeypatch):
    """If the connection response lacks referenceId, the KeyError still triggers connection cleanup."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.post.side_effect = [{"_id": "conn-real"}]

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(KeyError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-real")
    mock_client.patch.assert_not_called()


def test_locale_list_empty_raises_and_cleans_up_connection(mock_client, state, cache, monkeypatch):
    """If the project has no locales configured, a clear ValueError is raised
    instead of an unguarded IndexError, and the connection is still cleaned up."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.post.side_effect = [{"_id": "conn-real", "referenceId": "conn-ref-real"}]
    mock_client.patch.side_effect = [{}]
    mock_client.get.return_value = {"items": []}

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ValueError, match="no locales configured"):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-real")


def test_provision_webrtc_endpoint_missing_project_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "project_id" for d in data["details"])


def test_provision_webrtc_endpoint_missing_flow_reference_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "flow_reference_id" for d in data["details"])


def test_default_connection_type_and_fields_are_azure(mock_client, state, cache, monkeypatch):
    """Omitting connection_type/connection_fields preserves today's Azure default shape."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["type"] == "MicrosoftSpeechProvider"
    assert conn_body["fields"] == {"apiKey": "dummy", "region": "australiaeast"}


def test_generic_connection_type_and_fields_pass_through(mock_client, state, cache, monkeypatch):
    """A caller-supplied connection_type/connection_fields flows through untouched, proving genericity."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "connection_type": "SomeOtherProvider",
        "connection_fields": {"foo": "bar", "baz": "qux"},
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["type"] == "SomeOtherProvider"
    assert conn_body["fields"] == {"apiKey": "dummy", "foo": "bar", "baz": "qux"}


def test_connection_fields_cannot_override_api_key(mock_client, state, cache, monkeypatch):
    """A caller-supplied connection_fields={'apiKey': ...} must never override the real API key."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-secret-key")
    _args(mock_client)

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "connection_fields": {"apiKey": "attacker-supplied", "region": "eastus"},
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["fields"]["apiKey"] == "real-secret-key"
    assert conn_body["fields"]["region"] == "eastus"
