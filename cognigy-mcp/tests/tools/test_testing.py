import json
import pytest
import httpx
import respx
from cognigy_mcp.tools.testing import make_handlers, TOOLS
from cognigy_mcp.api import CognigyClient

ENDPOINT_BASE = "https://cognigy-endpoint-au1.nicecxone.com"


@pytest.fixture
def real_client():
    return CognigyClient(
        base_url="https://cognigy-api-au1.nicecxone.com",
        api_key="test-key",
    )


def test_tool_exported():
    assert any(t.name == "talk_to_agent" for t in TOOLS)


def test_talk_to_agent_uses_endpoint_base(real_client, state, cache):
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "Hello!", "data": {}, "type": "output"
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
        })
    data = json.loads(result[0].text)
    assert data["text"] == "Hello!"


def test_talk_to_agent_missing_token_and_flow_id(real_client, state, cache):
    handlers = make_handlers(real_client, state, cache)
    result = handlers["talk_to_agent"]({
        "message": "Hi",
        "session_id": "sess-1",
        "user_id": "user-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_talk_to_agent_flow_id_lookup(real_client, state, cache):
    """Should resolve endpoint token from state when flow_id is given."""
    # Populate state the same way sync_remote_state does
    state.set("endpoints", "My REST Endpoint", value={
        "id": "ep-1",
        "urlToken": "tok-from-state",
        "flowReferenceId": "flow-abc",
    })
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok-from-state").mock(
            return_value=httpx.Response(200, json={"text": "Response!", "data": {}})
        )
        result = handlers["talk_to_agent"]({
            "message": "Hello",
            "flow_id": "flow-abc",
            "session_id": "sess-2",
            "user_id": "user-2",
        })
    data = json.loads(result[0].text)
    assert data["text"] == "Response!"


def test_talk_to_agent_flow_id_not_found_shows_known_endpoints(real_client, state, cache):
    """Error message should list known endpoints when flow_id lookup fails."""
    state.set("endpoints", "Known Endpoint", value={
        "id": "ep-1", "urlToken": "tok1", "flowReferenceId": "other-flow",
    })
    handlers = make_handlers(real_client, state, cache)
    result = handlers["talk_to_agent"]({
        "message": "Hi",
        "flow_id": "nonexistent-flow",
        "session_id": "sess-3",
        "user_id": "user-3",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Known Endpoint" in data["error"]


def test_talk_to_agent_minimal_returns_text(real_client, state, cache):
    """minimal=True should return the text field from the response."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "How can I help with your parts enquiry?",
                "data": {},
                "sessionId": "sess-1",
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "How can I help with your parts enquiry?"
    assert data["sessionId"] == "sess-1"


def test_talk_to_agent_minimal_text_field_wins_over_outputs_array(real_client, state, cache):
    """When text is present at top level, it takes priority over outputs[] array."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "Hello there",
                "outputs": [{"text": "This should not win", "type": "output"}],
                "data": {},
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "Hello there"


def test_talk_to_agent_minimal_with_outputs_array(real_client, state, cache):
    """minimal=True should extract text from outputs[] array when top-level text absent."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "outputs": [
                    {"text": "Array output text", "type": "output"},
                ],
                "sessionId": "sess-1",
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "Array output text"


def test_talk_to_agent_sends_data_param_in_payload(real_client, state, cache):
    """data param must be forwarded in the REST POST body."""
    handlers = make_handlers(real_client, state, cache)
    captured = {}
    with respx.mock:
        def capture(request):
            import json
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"text": "ok", "data": {}})
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(side_effect=capture)
        handlers["talk_to_agent"]({
            "message": "",
            "endpoint_token": "tok123",
            "session_id": "sess-data",
            "user_id": "user-data",
            "data": {"selectedStore": "Repco Cheltenham", "selectedQuantity": 2},
        })
    assert captured["body"]["data"] == {
        "selectedStore": "Repco Cheltenham",
        "selectedQuantity": 2,
    }, "data param must be forwarded to POST body"
    assert captured["body"]["text"] == "", "message defaults to empty string"


def test_talk_to_agent_data_defaults_to_empty_dict_when_omitted(real_client, state, cache):
    """When data is not provided, POST body must have data: {}."""
    handlers = make_handlers(real_client, state, cache)
    captured = {}
    with respx.mock:
        def capture(request):
            import json
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"text": "Hi!", "data": {}})
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(side_effect=capture)
        handlers["talk_to_agent"]({
            "message": "Hello",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
        })
    assert captured["body"]["data"] == {}, "data must default to {}"


def test_talk_to_agent_message_optional_when_data_provided(real_client, state, cache):
    """talk_to_agent must not raise when message is absent and data is provided."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={"text": "Noted.", "data": {}})
        )
        # No "message" key at all — should not raise KeyError
        result = handlers["talk_to_agent"]({
            "endpoint_token": "tok123",
            "session_id": "sess-xapp",
            "user_id": "user-xapp",
            "data": {"xappField": "value"},
        })
    data = json.loads(result[0].text)
    assert "error" not in data, f"Should not error on missing message: {data}"
