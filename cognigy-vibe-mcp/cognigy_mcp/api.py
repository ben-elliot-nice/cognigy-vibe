from __future__ import annotations
import httpx
import tenacity
from tenacity import retry, retry_if_exception_type, stop_after_attempt


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class RetriableApiError(ApiError):
    def __init__(self, status_code: int, message: str, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(status_code, message)


def _retry_wait(retry_state: tenacity.RetryCallState) -> float:
    exc = retry_state.outcome.exception()
    if isinstance(exc, RetriableApiError) and exc.retry_after is not None:
        return max(exc.retry_after, 1.0)
    return min(2 ** (retry_state.attempt_number - 1), 30)


_RETRY = retry(
    retry=retry_if_exception_type(RetriableApiError),
    stop=stop_after_attempt(3),
    wait=_retry_wait,
    reraise=True,
)


class CognigyClient:
    def __init__(self, base_url: str, api_key: str):
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()

    @property
    def endpoint_base_url(self) -> str:
        # cognigy-api-au1.nicecxone.com → cognigy-endpoint-au1.nicecxone.com
        if "cognigy-api-" not in self._base:
            raise ValueError(
                f"Cannot derive endpoint URL from base_url '{self._base}'. "
                "Expected a URL containing 'cognigy-api-' (e.g. cognigy-api-au1.nicecxone.com)"
            )
        return self._base.replace("cognigy-api-", "cognigy-endpoint-")

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
            msg = body.get("error") or body.get("message") or resp.text
        except (ValueError, AttributeError):
            msg = resp.text
        if resp.status_code == 429:
            raw = resp.headers.get("Retry-After")
            try:
                retry_after = float(raw)
            except (TypeError, ValueError):
                retry_after = None
            raise RetriableApiError(resp.status_code, msg, retry_after=retry_after)
        if resp.status_code in (500, 502, 503, 504):
            raise RetriableApiError(resp.status_code, msg, retry_after=None)
        raise ApiError(resp.status_code, msg)

    @_RETRY
    def get(self, path: str, **params) -> dict:
        resp = self._http.get(self._base + path, params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    def post(self, path: str, body: dict, *, retry: bool = True) -> dict:
        """retry=False for non-idempotent creates with no server-side dedupe, where a
        5xx received after the write actually committed would retry into a duplicate
        (e.g. provisioning a connection/endpoint by name)."""
        if retry:
            return self._post_retrying(path, body)
        return self._post_once(path, body)

    def _post_once(self, path: str, body: dict) -> dict:
        resp = self._http.post(self._base + path, json=body)
        self._raise_for_status(resp)
        return resp.json()

    @_RETRY
    def _post_retrying(self, path: str, body: dict) -> dict:
        return self._post_once(path, body)

    @_RETRY
    def patch(self, path: str, body: dict) -> dict:
        resp = self._http.patch(self._base + path, json=body)
        self._raise_for_status(resp)
        if resp.status_code == 204:
            return {}
        return resp.json()

    def post_multipart(
        self, path: str, *, files: dict, data: dict | None = None, retry: bool = False,
    ) -> dict:
        """retry defaults to False: file uploads are non-idempotent creates with no
        server-side dedupe, so a 5xx received after the write actually committed
        would retry into a duplicate Knowledge Source."""
        if retry:
            return self._post_multipart_retrying(path, files, data)
        return self._post_multipart_once(path, files, data)

    def _post_multipart_once(self, path: str, files: dict, data: dict | None) -> dict:
        resp = self._http.post(self._base + path, files=files, data=data or {})
        self._raise_for_status(resp)
        return resp.json()

    @_RETRY
    def _post_multipart_retrying(self, path: str, files: dict, data: dict | None) -> dict:
        return self._post_multipart_once(path, files, data)

    @_RETRY
    def delete(self, path: str) -> dict:
        resp = self._http.delete(self._base + path)
        try:
            self._raise_for_status(resp)
        except ApiError as e:
            if e.status_code == 404:
                return {}
            raise
        try:
            return resp.json()
        except Exception:
            return {}

    @_RETRY
    def download_url(self, url: str) -> bytes:
        """GET an absolute URL and return raw bytes. Used for pre-signed download URLs
        that are not routed through the Cognigy API base path. Sends Accept: */* to
        avoid the default application/json header interfering with binary responses."""
        # Pre-signed URLs typically have short TTLs; 5xx retries are safe because the URL
        # has not been consumed on failure, but a large Retry-After could outlive the TTL.
        resp = self._http.get(url, headers={"Accept": "*/*"})
        self._raise_for_status(resp)
        return resp.content

    def get_openapi_spec(self) -> dict:
        """GET the live OpenAPI spec using the same X-API-Key auth as every other call —
        no session cookie required."""
        return self.get("/openapi/openapi-viewer.json")
