"""WordPress HTML + CSS scraper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class ScrapedPage:
    slug: str
    url: str
    html: str
    css: str


class WpScraper:
    def __init__(
        self,
        base_url: str,
        internal_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_url = (internal_url or base_url).rstrip("/")
        self.timeout = timeout

    def fetch_page(self, path: str) -> ScrapedPage:
        url = urljoin(self.internal_url + "/", path.lstrip("/"))
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        html = resp.text
        css = self._extract_css(html, url)
        slug = self._slug_from_path(path)
        return ScrapedPage(slug=slug, url=url, html=html, css=css)

    def _extract_css(self, html: str, page_url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        parts: list[str] = []
        for style in soup.find_all("style"):
            if style.string:
                parts.append(style.string)
        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if not href:
                continue
            if isinstance(href, list):
                href = href[0] if href else ""
            if not href:
                continue
            css_url = urljoin(page_url, href)
            try:
                r = requests.get(css_url, timeout=self.timeout)
                if r.status_code == 200:
                    parts.append(r.text)
            except requests.RequestException:
                continue
        return "\n\n".join(parts)

    def _slug_from_path(self, path: str) -> str:
        parsed = urlparse(path)
        slug = parsed.path.strip("/").replace("/", "-")
        return slug or "index"

    @staticmethod
    def save_page(page: ScrapedPage, dump_dir: Path) -> None:
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / f"{page.slug}.html").write_text(page.html, encoding="utf-8")
        (dump_dir / f"{page.slug}.css").write_text(page.css, encoding="utf-8")
