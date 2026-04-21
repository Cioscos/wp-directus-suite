#!/usr/bin/env python3
"""Detect Polylang/WPML + generate react-i18next locales."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from lib.env_loader import load_dotenv
from lib.state_store import StateStore


def _detect_polylang(base_url: str, timeout: int = 10) -> list[str] | None:
    try:
        r = requests.get(f"{base_url}/wp-json/pll/v1/languages", timeout=timeout)
        if r.status_code == 200:
            data: list[dict[str, Any]] = r.json()
            return [str(item["slug"]) for item in data if "slug" in item]
    except requests.RequestException:
        return None
    return None


def _fetch_posts_for_language(base_url: str, lang: str, timeout: int = 30) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {"lang": lang, "per_page": 100}
    try:
        r = requests.get(
            f"{base_url}/wp-json/wp/v2/posts",
            params=params,
            timeout=timeout,
        )
        if r.status_code == 200:
            data: list[dict[str, Any]] = r.json()
            return data
    except requests.RequestException:
        return []
    return []


def _build_translation_dict(posts: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in posts:
        pid = p.get("id")
        title_field = p.get("title")
        title = title_field.get("rendered") if isinstance(title_field, dict) else title_field
        if pid and isinstance(title, str):
            out[f"post.{pid}.title"] = title
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    env = load_dotenv(args.env_file)
    env.update({k: v for k, v in os.environ.items() if k.startswith("WP_")})
    base_url = (env.get("WP_SITE_URL") or env.get("WP_INTERNAL_URL") or "").rstrip("/")

    store = StateStore(args.state_file)

    if not base_url:
        print("WARN: nessun WP URL configurato, skip i18n.")
        store.update({"phase": "verify", "i18n_enabled": False})
        return 0

    langs = _detect_polylang(base_url)
    if not langs:
        print("i18n: nessun multi-lingua rilevato (Polylang assente).")
        store.update({"phase": "verify", "i18n_enabled": False})
        return 0

    locales_dir = args.output_dir / "src" / "locales"
    for lang in langs:
        posts = _fetch_posts_for_language(base_url, lang)
        translations = _build_translation_dict(posts)
        dest_dir = locales_dir / lang
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "translation.json").write_text(
            json.dumps(translations, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    store.update(
        {
            "phase": "verify",
            "i18n_enabled": True,
            "i18n_locales": langs,
        }
    )
    print(f"gen_i18n OK. Locales: {', '.join(langs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
