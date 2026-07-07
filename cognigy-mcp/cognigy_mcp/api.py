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
        return exc.retry_after
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
            headers={"X-API-Key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
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
        except Exception:
            msg = resp.text
        if resp.status_code == 429:
            raw = resp.headers.get("Retry-After")
            retry_after = float(raw) if raw is not None else None
            raise RetriableApiError(resp.status_code, msg, retry_after=retry_after)
        if resp.status_code >= 500:
            raise RetriableApiError(resp.status_code, msg, retry_after=None)
        raise ApiError(resp.status_code, msg)

    @_RETRY
    def get(self, path: str, **params) -> dict:
        resp = self._http.get(self._base + path, params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    @_RETRY
    def post(self, path: str, body: dict) -> dict:
        resp = self._http.post(self._base + path, json=body)
        self._raise_for_status(resp)
        return resp.json()

    @_RETRY
    def patch(self, path: str, body: dict) -> dict:
        resp = self._http.patch(self._base + path, json=body)
        self._raise_for_status(resp)
        if resp.status_code == 204:
            return {}
        return resp.json()

    @_RETRY
    def delete(self, path: str) -> dict:
        resp = self._http.delete(self._base + path)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except Exception:
            return {}

    @_RETRY
    def download_url(self, url: str) -> bytes:
        """GET an absolute URL and return raw bytes. Used for pre-signed download URLs
        that are not routed through the Cognigy API base path. Sends Accept: */* to
        avoid the default application/json header interfering with binary responses."""
        resp = self._http.get(url, headers={"Accept": "*/*"})
        self._raise_for_status(resp)
        return resp.content
