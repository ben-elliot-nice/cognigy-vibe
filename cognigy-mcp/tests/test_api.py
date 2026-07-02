import pytest
import httpx
import respx
from cognigy_mcp.api import CognigyClient, ApiError

BASE = "https://cognigy-api-au1.nicecxone.com"


@pytest.fixture
def client():
    return CognigyClient(base_url=BASE, api_key="test-key")


def test_endpoint_base_url_derivation(client):
    assert client.endpoint_base_url == "https://cognigy-endpoint-au1.nicecxone.com"


def test_get_success(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={"_id": "flow-123", "name": "Test"})
        )
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"


def test_get_401_raises_api_error(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/bad").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/bad")
    assert exc.value.status_code == 401


def test_get_404_raises_api_error(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/missing").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/missing")
    assert exc.value.status_code == 404


def test_post_success(client):
    with respx.mock:
        respx.post(f"{BASE}/v2.0/flows").mock(
            return_value=httpx.Response(200, json={"_id": "new-flow", "name": "My Flow"})
        )
        result = client.post("/v2.0/flows", {"name": "My Flow", "projectId": "proj-1"})
    assert result["_id"] == "new-flow"


def test_patch_success(client):
    with respx.mock:
        respx.patch(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={"_id": "flow-123", "name": "Updated"})
        )
        result = client.patch("/v2.0/flows/flow-123", {"name": "Updated"})
    assert result["name"] == "Updated"


def test_patch_204_no_content_returns_empty_dict(client):
    """PATCH returning 204 No Content must not raise and must return {}."""
    with respx.mock:
        respx.patch(f"{BASE}/v2.0/flows/flow-123/chart/nodes/node-1").mock(
            return_value=httpx.Response(204)
        )
        result = client.patch("/v2.0/flows/flow-123/chart/nodes/node-1", {"label": "Updated"})
    assert result == {}


def test_delete_success(client):
    with respx.mock:
        respx.delete(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={})
        )
        result = client.delete("/v2.0/flows/flow-123")
    assert result == {}


def test_auth_header_sent(client):
    with respx.mock:
        route = respx.get(f"{BASE}/v2.0/flows").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        client.get("/v2.0/flows")
    assert route.calls[0].request.headers["X-API-Key"] == "test-key"


def test_non_json_error_body_raises_api_error(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/bad").mock(
            return_value=httpx.Response(
                500,
                content=b"Internal Server Error",
                headers={"content-type": "text/plain"},
            )
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/bad")
    assert exc.value.status_code == 500
    assert "Internal Server Error" in str(exc.value)


def test_endpoint_base_url_raises_for_non_matching_url():
    c = CognigyClient(base_url="https://localhost:8080", api_key="key")
    with pytest.raises(ValueError, match="cognigy-api-"):
        _ = c.endpoint_base_url


def test_download_success(client):
    """download() returns raw bytes from the response body."""
    zip_bytes = b"PK\x03\x04fake-zip-content"
    with respx.mock:
        respx.get(f"{BASE}/v2.0/packages/pkg-1/download").mock(
            return_value=httpx.Response(200, content=zip_bytes)
        )
        result = client.download("/v2.0/packages/pkg-1/download")
    assert result == zip_bytes


def test_download_error_raises_api_error(client):
    """download() raises ApiError on HTTP 4xx/5xx."""
    with respx.mock:
        respx.get(f"{BASE}/v2.0/packages/missing/download").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ApiError) as exc:
            client.download("/v2.0/packages/missing/download")
    assert exc.value.status_code == 404
