"""Directus REST client (stdlib only: urllib). Includes retry + idempotency helpers."""

import json
import time
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class DirectusClient:
    def __init__(self, base_url: str, token: str,
                 timeout: int = 30, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = retries

    def _request(self, method: str, endpoint: str, data: Any = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        delays = [1, 3, 9][: self.retries]
        last: Optional[Exception] = None
        for attempt, delay in enumerate([0] + delays):
            if delay:
                time.sleep(delay)
            req = Request(url, data=body, method=method)
            req.add_header("Authorization", f"Bearer {self.token}")
            if body is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    return raw
            except HTTPError as e:
                code = e.code
                if 400 <= code < 500 and code != 429:
                    msg = e.read().decode("utf-8", errors="replace")[:300]
                    raise RuntimeError(f"HTTP {code} {method} {endpoint}: {msg}") from e
                last = e
            except URLError as e:
                last = e
        raise RuntimeError(f"Request failed after {self.retries} retries: {last}")

    def get(self, endpoint: str) -> Any:
        raw = self._request("GET", endpoint)
        if not raw.strip():
            return None
        obj = json.loads(raw)
        return obj.get("data")

    def post(self, endpoint: str, data: Any) -> Any:
        raw = self._request("POST", endpoint, data)
        return json.loads(raw).get("data") if raw.strip() else None

    def patch(self, endpoint: str, data: Any) -> Any:
        raw = self._request("PATCH", endpoint, data)
        return json.loads(raw).get("data") if raw.strip() else None

    def ping(self) -> bool:
        try:
            raw = self._request("GET", "/server/ping")
            return "pong" in raw
        except Exception:
            return False

    def find_by_wp_id(self, collection: str, wp_id: int) -> Optional[int]:
        q = f"/items/{collection}?filter[wp_original_id][_eq]={quote(str(wp_id))}&limit=1"
        data = self.get(q)
        if data and len(data) > 0:
            return data[0]["id"]
        return None

    def list_all(self, collection: str, fields: str = "id,wp_original_id") -> list:
        q = f"/items/{collection}?fields={fields}&limit=-1"
        return self.get(q) or []
