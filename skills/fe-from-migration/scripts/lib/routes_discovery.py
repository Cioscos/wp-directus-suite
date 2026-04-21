"""WordPress routes discovery via REST + MySQL fallback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests


@dataclass
class Route:
    slug: str
    url: str
    collection: str
    template_type: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)


class RoutesDiscovery:
    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def discover_rest(self) -> list[Route]:
        """Discover routes via WP REST API.

        Raises requests.HTTPError on `/wp-json/wp/v2/types` failure.
        Caller should catch and fall back to `discover_mysql()` if appropriate.
        Per-type item fetch failures (non-200) are silently skipped.
        """
        types_url = f"{self.base_url}/wp-json/wp/v2/types"
        types_resp = requests.get(types_url, timeout=self.timeout)
        types_resp.raise_for_status()
        types_payload: dict[str, Any] = types_resp.json()

        routes: list[Route] = []
        for type_key, type_data in types_payload.items():
            if not isinstance(type_data, dict):
                continue
            rest_base = type_data.get("rest_base")
            if not rest_base:
                continue
            items_url = f"{self.base_url}/wp-json/wp/v2/{rest_base}"
            items_resp = requests.get(items_url, timeout=self.timeout, params={"per_page": 100})
            if items_resp.status_code != 200:
                continue
            for item in items_resp.json():
                slug = item.get("slug")
                if not slug:
                    continue
                link = item.get("link") or ""
                path = urlparse(link).path or f"/{slug}"
                url = link or f"{self.base_url}{path}"
                routes.append(
                    Route(
                        slug=slug,
                        url=url,
                        collection=rest_base,
                        template_type=type_key,
                        metadata={"id": item.get("id"), "path": path},
                    )
                )
        return routes

    def discover_mysql(
        self,
        mysql_runner: Callable[[str], list[dict[str, Any]]],
    ) -> list[Route]:
        """Fallback when REST unavailable. mysql_runner executes SQL and returns rows."""
        query = (
            "SELECT ID, post_name, post_type, post_parent "
            "FROM wp_posts WHERE post_status='publish' "
            "AND post_type NOT IN ('revision','attachment','nav_menu_item')"
        )
        rows = mysql_runner(query)
        routes: list[Route] = []
        for row in rows:
            slug = row.get("post_name")
            post_type = row.get("post_type", "post")
            if not slug:
                continue
            collection = f"{post_type}s" if not post_type.endswith("s") else post_type
            routes.append(
                Route(
                    slug=slug,
                    url=f"{self.base_url}/{slug}",
                    collection=collection,
                    template_type=post_type,
                    metadata={"id": row.get("ID"), "parent": row.get("post_parent")},
                )
            )
        return routes
