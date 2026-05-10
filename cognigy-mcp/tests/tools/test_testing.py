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
