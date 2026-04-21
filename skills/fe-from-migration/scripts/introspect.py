#!/usr/bin/env python3
"""Introspect Directus schema via REST."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from lib.directus_client import DirectusClient
from lib.env_loader import load_dotenv
from lib.state_store import StateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--schema-file", required=True, type=Path)
    args = parser.parse_args(argv)

    env = load_dotenv(args.env_file)
    env.update({k: v for k, v in os.environ.items() if k.startswith("DIRECTUS_")})

    directus_url = env.get("DIRECTUS_URL")
    token = env.get("DIRECTUS_TOKEN")
    if not directus_url or not token:
        print("ERRORE: DIRECTUS_URL o DIRECTUS_TOKEN mancanti.", file=sys.stderr)
        return 1

    client = DirectusClient(directus_url, token)
    collections_names = client.list_collections()

    schema_collections: list[dict[str, Any]] = []
    for name in collections_names:
        fields_raw = client.list_fields(name)
        fields = [
            {
                "name": f["field"],
                "type": f.get("type", "unknown"),
                "interface": f.get("meta", {}).get("interface"),
                "relation": (
                    f.get("schema", {}).get("foreign_key_table") if f.get("schema") else None
                ),
            }
            for f in fields_raw
        ]
        schema_collections.append({"name": name, "fields": fields})

    schema = {"collections": schema_collections}
    args.schema_file.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    store = StateStore(args.state_file)
    store.set("phase", "gen_scaffold")
    print(f"introspect OK. {len(collections_names)} collections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
