import json
import pytest
from unittest.mock import PropertyMock
from cognigy_mcp.api import ApiError
from cognigy_mcp.tools.voice_ops import make_handlers, TOOLS


def test_tool_exported():
    names = [t.name for t in TOOLS]
    assert "provision_webrtc_endpoint" in names


def test_real_creds_path(mock_client, state, cache, monkeypatch):
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.post.side_effect = [
        {"_id": "conn-1"},
        {"_id": "ep-1", "URLToken": "tok123"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_id": "flow-hex",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "region": "australiaeast",
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
    mock_client.post.side_effect = [
        {"_id": "conn-dummy"},
        {"_id": "ep-2", "URLToken": "tok456"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_id": "flow-hex",
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
    mock_client.post.side_effect = [
        {"_id": "conn-dummy"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_id": "fid",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "region": "australiaeast",
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["fields"]["apiKey"] == "dummy"
    assert conn_body["fields"]["region"] == "australiaeast"


def test_real_creds_path_sends_real_api_key(mock_client, state, cache, monkeypatch):
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "my-real-key")
    mock_client.post.side_effect = [
        {"_id": "conn-real"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_id": "fid",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
        "region": "australiaeast",
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["fields"]["apiKey"] == "my-real-key"


def test_endpoint_post_body(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    mock_client.post.side_effect = [
        {"_id": "conn-1"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_id": "fid-hex",
        "flow_reference_id": "fref-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })

    ep_body = mock_client.post.call_args_list[1][0][1]
    assert ep_body["channel"] == "voiceGateway2"
    assert ep_body["flowId"] == "fid-hex"
    assert ep_body["flowReferenceId"] == "fref-uuid"
    assert ep_body["webrtcWidgetConfig"] == {"active": True}
    assert ep_body["name"] == "Click-to-Call"


def test_urltoken_lowercase_fallback(mock_client, state, cache, monkeypatch):
    """Handles lowercase urlToken returned by some environments."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    mock_client.post.side_effect = [
        {"_id": "conn-1"},
        {"_id": "ep-1", "urlToken": "lower-tok"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "p", "flow_id": "f", "flow_reference_id": "r",
        "endpoint_name": "Click-to-Call", "connection_name": "Test",
    })
    data = json.loads(result[0].text)
    assert data["url_token"] == "lower-tok"
    assert "lower-tok" in data["demo_url"]


def test_connection_post_body(mock_client, state, cache, monkeypatch):
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    mock_client.post.side_effect = [
        {"_id": "conn-1"},
        {"_id": "ep-1", "URLToken": "tok"},
    ]
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"

    handlers = make_handlers(mock_client, state, cache)
    handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-abc",
        "flow_id": "fid",
        "flow_reference_id": "fref",
        "endpoint_name": "Click-to-Call",
        "connection_name": "MyConn",
        "region": "eastus",
    })

    conn_body = mock_client.post.call_args_list[0][0][1]
    assert conn_body["name"] == "MyConn"
    assert conn_body["extension"] == "@cognigy/audio-preview-provider"
    assert conn_body["type"] == "MicrosoftSpeechProvider"
    assert conn_body["resourceLevel"] == "project"
    assert conn_body["projectId"] == "proj-abc"
    assert conn_body["fields"]["region"] == "eastus"


def test_endpoint_base_url_raises_propagates_before_api_calls(mock_client, state, cache, monkeypatch):
    """ValueError from endpoint_base_url raises immediately — no API calls made."""
    monkeypatch.delenv("COGNIGY_VOICE_PREVIEW_API_KEY", raising=False)
    type(mock_client).endpoint_base_url = PropertyMock(side_effect=ValueError("no cognigy-api- in URL"))

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ValueError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "p", "flow_id": "f", "flow_reference_id": "r",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.post.assert_not_called()
    mock_client.delete.assert_not_called()


def test_endpoint_post_failure_cleans_up_connection(mock_client, state, cache, monkeypatch):
    """If endpoint POST raises, the speech connection is deleted before re-raising."""
    monkeypatch.setenv("COGNIGY_VOICE_PREVIEW_API_KEY", "real-key")
    mock_client.endpoint_base_url = "https://cognigy-endpoint-au1.nicecxone.com"
    mock_client.post.side_effect = [
        {"_id": "conn-real"},
        ApiError(500, "endpoint creation failed"),
    ]

    handlers = make_handlers(mock_client, state, cache)
    with pytest.raises(ApiError):
        handlers["provision_webrtc_endpoint"]({
            "project_id": "proj-1", "flow_id": "fid", "flow_reference_id": "fref",
            "endpoint_name": "Click-to-Call", "connection_name": "Test",
        })

    mock_client.delete.assert_called_once_with("/v2.0/connections/conn-real")


def test_provision_webrtc_endpoint_missing_project_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "flow_id": "flow-hex",
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
        "flow_id": "flow-hex",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "flow_reference_id" for d in data["details"])
