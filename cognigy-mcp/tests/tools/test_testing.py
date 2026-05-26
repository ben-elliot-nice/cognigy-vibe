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
