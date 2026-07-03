from __future__ import annotations
import httpx


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


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
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("error") or body.get("message") or resp.text
            except Exception:
                msg = resp.text
            raise ApiError(resp.status_code, msg)

    def get(self, path: str, **params) -> dict:
        resp = self._http.get(self._base + path, params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    def post(self, path: str, body: dict) -> dict:
        resp = self._http.post(self._base + path, json=body)
        self._raise_for_status(resp)
        return resp.json()

    def patch(self, path: str, body: dict) -> dict:
        resp = self._http.patch(self._base + path, json=body)
        self._raise_for_status(resp)
        if resp.status_code == 204:
            return {}
        return resp.json()

    def delete(self, path: str) -> dict:
        resp = self._http.delete(self._base + path)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except Exception:
            return {}

    def download_url(self, url: str) -> bytes:
        """GET an absolute URL and return raw bytes. Used for pre-signed download URLs
        that are not routed through the Cognigy API base path. Sends Accept: */* to
        avoid the default application/json header interfering with binary responses."""
        resp = self._http.get(url, headers={"Accept": "*/*"})
        self._raise_for_status(resp)
        return resp.content
