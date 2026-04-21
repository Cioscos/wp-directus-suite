"""Directus REST API client."""

from __future__ import annotations

import time
from typing import Any

import requests


class DirectusClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._request_with_retry("GET", url, params=params)
        data: dict[str, Any] = resp.json()
        return data

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> requests.Response:
        for attempt in range(max_retries):
            resp = requests.request(
                method, url, headers=self._headers(), params=params, timeout=self.timeout
            )
            if resp.status_code < 400:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
        raise RuntimeError("unreachable: retry loop exited without return or raise")

    def list_collections(self) -> list[str]:
        payload = self._get("/collections")
        data: list[dict[str, Any]] = payload.get("data", [])
        result: list[str] = []
        for c in data:
            name = c.get("collection")
            if isinstance(name, str) and name and not name.startswith("directus_"):
                result.append(name)
        return result

    def list_fields(self, collection: str) -> list[dict[str, Any]]:
        payload = self._get(f"/fields/{collection}")
        data: list[dict[str, Any]] = payload.get("data", [])
        return data

    def ping(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/server/ping",
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
