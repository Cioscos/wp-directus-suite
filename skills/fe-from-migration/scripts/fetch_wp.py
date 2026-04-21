#!/usr/bin/env python3
"""Fetch WP routes + scrape HTML/CSS + detect form plugins."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from lib.env_loader import load_dotenv
from lib.form_plugin_mapper import FormPluginMapper
from lib.routes_discovery import RoutesDiscovery
from lib.state_store import StateStore
from lib.wp_scraper import WpScraper


def _url_to_path(url: str, base_url: str, internal_url: str) -> str:
    # Prefer path-only from full URL
    parsed = urlparse(url)
    if parsed.path:
        return parsed.path
    # fallback: strip known prefixes
    for prefix in (base_url.rstrip("/"), internal_url.rstrip("/")):
        if url.startswith(prefix):
            return url[len(prefix) :] or "/"
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--dump-dir", required=True, type=Path)
    parser.add_argument("--routes-file", required=True, type=Path)
    parser.add_argument("--forms-file", required=True, type=Path)
    args = parser.parse_args(argv)

    env = load_dotenv(args.env_file)
    env.update({k: v for k, v in os.environ.items() if k.startswith("WP_")})

    base_url = env.get("WP_SITE_URL") or env.get("WP_INTERNAL_URL")
    if not base_url:
        print("ERRORE: WP_SITE_URL o WP_INTERNAL_URL non configurato.", file=sys.stderr)
        return 1

    internal_url = env.get("WP_INTERNAL_URL") or base_url
    args.dump_dir.mkdir(parents=True, exist_ok=True)
    store = StateStore(args.state_file)

    disc = RoutesDiscovery(base_url=base_url)
    routes = disc.discover_rest()

    if not routes:
        print(
            "WARN: nessuna route scoperta via REST. Fallback MySQL non auto-implementato in v1 — "
            "configura REST accessibile o compila state/routes.json manualmente.",
            file=sys.stderr,
        )
        return 2

    args.routes_file.write_text(
        json.dumps([asdict(r) for r in routes], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    scraper = WpScraper(base_url=base_url, internal_url=internal_url)
    form_mapper = FormPluginMapper()
    all_forms: list[dict[str, object]] = []

    for r in routes:
        if store.is_done("fetch_wp_routes", r.slug):
            continue
        try:
            path = _url_to_path(r.url, base_url, internal_url)
            page = scraper.fetch_page(path)
            scraper.save_page(page, args.dump_dir)
            for fm in form_mapper.detect(page.html):
                all_forms.append(
                    {
                        "route": r.slug,
                        "plugin": fm.plugin,
                        "fields": fm.fields,
                        "action": fm.action,
                    }
                )
            store.mark_done("fetch_wp_routes", r.slug)
        except Exception as e:  # isolate per-route failures (spec)
            err_file = args.dump_dir / "errors.log"
            try:
                with err_file.open("a", encoding="utf-8") as f:
                    f.write(f"{r.slug}: {e}\n")
            except OSError:
                pass  # errors.log best-effort

    args.forms_file.write_text(
        json.dumps(all_forms, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    store.set("phase", "analyze_style")
    print(f"fetch_wp OK. {len(routes)} routes elaborate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
