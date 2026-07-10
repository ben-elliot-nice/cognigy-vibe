import pytest
import httpx
import respx
from unittest.mock import patch
from cognigy_mcp.api import CognigyClient, ApiError, RetriableApiError

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


@patch("time.sleep")
def test_non_json_error_body_raises_api_error(mock_sleep, client):
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


# --- RetriableApiError exception hierarchy ---

def test_retriable_api_error_is_api_error():
    exc = RetriableApiError(429, "rate limited", retry_after=5.0)
    assert isinstance(exc, ApiError)
    assert exc.status_code == 429
    assert exc.retry_after == 5.0


def test_retriable_api_error_no_retry_after():
    exc = RetriableApiError(503, "unavailable")
    assert exc.retry_after is None


# --- _raise_for_status behaviour ---

def test_raise_for_status_429_with_retry_after_header(client):
    resp = httpx.Response(
        429,
        json={"error": "rate limited"},
        headers={"Retry-After": "3"},
    )
    with pytest.raises(RetriableApiError) as exc:
        client._raise_for_status(resp)
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 3.0


def test_raise_for_status_429_without_retry_after_header(client):
    resp = httpx.Response(429, json={"error": "rate limited"})
    with pytest.raises(RetriableApiError) as exc:
        client._raise_for_status(resp)
    assert exc.value.status_code == 429
    assert exc.value.retry_after is None


def test_raise_for_status_500_raises_retriable(client):
    resp = httpx.Response(500, json={"error": "server error"})
    with pytest.raises(RetriableApiError) as exc:
        client._raise_for_status(resp)
    assert exc.value.status_code == 500
    assert exc.value.retry_after is None


def test_raise_for_status_503_raises_retriable(client):
    resp = httpx.Response(503, text="Service Unavailable", headers={"content-type": "text/plain"})
    with pytest.raises(RetriableApiError) as exc:
        client._raise_for_status(resp)
    assert exc.value.status_code == 503


def test_raise_for_status_404_raises_plain_api_error(client):
    resp = httpx.Response(404, json={"error": "Not found"})
    with pytest.raises(ApiError) as exc:
        client._raise_for_status(resp)
    assert type(exc.value) is ApiError
    assert exc.value.status_code == 404


def test_raise_for_status_401_raises_plain_api_error(client):
    resp = httpx.Response(401, json={"error": "Unauthorized"})
    with pytest.raises(ApiError) as exc:
        client._raise_for_status(resp)
    assert type(exc.value) is ApiError
    assert exc.value.status_code == 401


def test_raise_for_status_501_raises_plain_api_error(client):
    resp = httpx.Response(501, json={"error": "not implemented"})
    with pytest.raises(ApiError) as exc:
        client._raise_for_status(resp)
    assert type(exc.value) is ApiError
    assert exc.value.status_code == 501


def test_raise_for_status_429_with_http_date_retry_after_falls_back_to_none(client):
    resp = httpx.Response(
        429,
        json={"error": "rate limited"},
        headers={"Retry-After": "Wed, 09 Jul 2025 12:00:00 GMT"},
    )
    with pytest.raises(RetriableApiError) as exc:
        client._raise_for_status(resp)
    assert exc.value.status_code == 429
    assert exc.value.retry_after is None


# --- Retry integration tests ---

@patch("time.sleep")
def test_get_retries_on_5xx_and_succeeds(mock_sleep, client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(side_effect=[
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(200, json={"_id": "flow-123"}),
        ])
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"
    assert mock_sleep.call_count == 1


@patch("time.sleep")
def test_get_raises_after_3_failed_attempts(mock_sleep, client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        with pytest.raises(RetriableApiError) as exc:
            client.get("/v2.0/flows/flow-123")
    assert exc.value.status_code == 503
    assert mock_sleep.call_count == 2


@patch("time.sleep")
def test_get_429_respects_retry_after_header(mock_sleep, client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(side_effect=[
            httpx.Response(429, json={"error": "rate limited"}, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"_id": "flow-123"}),
        ])
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"
    mock_sleep.assert_called_once_with(7.0)


@patch("time.sleep")
def test_get_429_without_retry_after_uses_exponential_backoff(mock_sleep, client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(side_effect=[
            httpx.Response(429, json={"error": "rate limited"}),
            httpx.Response(200, json={"_id": "flow-123"}),
        ])
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"
    mock_sleep.assert_called_once_with(1.0)


def test_get_404_does_not_retry(client):
    with respx.mock:
        route = respx.get(f"{BASE}/v2.0/flows/missing").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/missing")
    assert exc.value.status_code == 404
    assert route.call_count == 1


@patch("time.sleep")
def test_download_url_retries_on_5xx_and_succeeds(mock_sleep, client):
    presigned = "https://storage.example.com/packages/export.zip"
    zip_bytes = b"PK\x03\x04fake-zip-content"
    with respx.mock:
        respx.get(presigned).mock(side_effect=[
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(200, content=zip_bytes),
        ])
        result = client.download_url(presigned)
    assert result == zip_bytes
    assert mock_sleep.call_count == 1


def test_endpoint_base_url_raises_for_non_matching_url():
    c = CognigyClient(base_url="https://localhost:8080", api_key="key")
    with pytest.raises(ValueError, match="cognigy-api-"):
        _ = c.endpoint_base_url


def test_download_url_success(client):
    """download_url() returns raw bytes from a pre-signed absolute URL."""
    zip_bytes = b"PK\x03\x04fake-zip-content"
    presigned = "https://storage.example.com/packages/export.zip"
    with respx.mock:
        respx.get(presigned).mock(
            return_value=httpx.Response(200, content=zip_bytes)
        )
        result = client.download_url(presigned)
    assert result == zip_bytes


def test_download_url_sends_accept_any(client):
    """download_url() must override Accept to */* to avoid the default application/json header."""
    presigned = "https://storage.example.com/packages/export.zip"
    with respx.mock:
        route = respx.get(presigned).mock(
            return_value=httpx.Response(200, content=b"zip")
        )
        client.download_url(presigned)
    assert route.calls[0].request.headers["Accept"] == "*/*"


def test_download_url_error_raises_api_error(client):
    """download_url() raises ApiError on HTTP 4xx/5xx."""
    presigned = "https://storage.example.com/packages/missing.zip"
    with respx.mock:
        respx.get(presigned).mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ApiError) as exc:
            client.download_url(presigned)
    assert exc.value.status_code == 404


@patch("time.sleep")
def test_get_429_with_zero_retry_after_uses_floor(mock_sleep, client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(side_effect=[
            httpx.Response(429, json={"error": "rate limited"}, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"_id": "flow-123"}),
        ])
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"
    mock_sleep.assert_called_once_with(1.0)


@patch("time.sleep")
def test_post_5xx_retries_and_succeeds(mock_sleep, client):
    with respx.mock:
        respx.post(f"{BASE}/v2.0/flows").mock(side_effect=[
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(201, json={"_id": "flow-123"}),
        ])
        result = client.post("/v2.0/flows", {"name": "Test"})
    assert result["_id"] == "flow-123"
    assert mock_sleep.call_count == 1


@patch("time.sleep")
def test_post_5xx_raises_after_exhausting_retries(mock_sleep, client):
    with respx.mock:
        route = respx.post(f"{BASE}/v2.0/flows").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        with pytest.raises(ApiError) as exc:
            client.post("/v2.0/flows", {"name": "Test"})
    assert exc.value.status_code == 503
    assert route.call_count == 3


def test_post_retry_false_does_not_retry_on_5xx(client):
    """Non-idempotent creates with no server-side dedupe (e.g. provisioning a
    connection/endpoint by name) must not retry a 5xx into a duplicate create."""
    with respx.mock:
        route = respx.post(f"{BASE}/v2.0/connections").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        with pytest.raises(ApiError) as exc:
            client.post("/v2.0/connections", {"name": "Test"}, retry=False)
    assert exc.value.status_code == 503
    assert route.call_count == 1


def test_delete_404_treated_as_success(client):
    with respx.mock:
        respx.delete(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        result = client.delete("/v2.0/flows/flow-123")
    assert result == {}
