#!/usr/bin/env python3
"""Validate .env + ping Directus and WP source."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from lib.env_loader import load_dotenv
from lib.state_store import StateStore

REQUIRED_BASE = ["DIRECTUS_URL", "DIRECTUS_TOKEN"]


def _wp_source_configured(env: dict[str, str]) -> bool:
    return any(env.get(k) for k in ("WP_SITE_URL", "WP_STATIC_DUMP_PATH", "WP_INTERNAL_URL"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["test", "external"])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    args = parser.parse_args(argv)

    env = load_dotenv(args.env_file)
    env.update({k: v for k, v in os.environ.items() if k.startswith(("DIRECTUS_", "WP_"))})

    missing = [k for k in REQUIRED_BASE if not env.get(k)]
    if missing:
        print(f"ERRORE: variabili mancanti in .env: {', '.join(missing)}", file=sys.stderr)
        return 1

    if not _wp_source_configured(env):
        print(
            "ERRORE: configura WP_SITE_URL o WP_STATIC_DUMP_PATH o WP_INTERNAL_URL in .env",
            file=sys.stderr,
        )
        return 1

    directus_url = env["DIRECTUS_URL"].rstrip("/")
    try:
        r = requests.get(f"{directus_url}/server/ping", timeout=10)
        if r.status_code != 200:
            print(f"ERRORE: Directus ping fallito ({r.status_code})", file=sys.stderr)
            return 2
    except requests.RequestException as e:
        print(f"ERRORE: Directus non raggiungibile: {e}", file=sys.stderr)
        return 2

    wp_url = env.get("WP_SITE_URL")
    if wp_url:
        try:
            r = requests.get(wp_url, timeout=10)
            if r.status_code >= 500:
                print(f"WARNING: WP live URL ritorna {r.status_code}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"WARNING: WP URL non raggiungibile: {e}", file=sys.stderr)

    store = StateStore(args.state_file)
    store.set("phase", "mcp_install")
    print("env_check OK. Passo a mcp_install.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
