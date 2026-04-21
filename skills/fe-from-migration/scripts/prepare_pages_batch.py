#!/usr/bin/env python3
"""Prepare batch JSON for gen_pages phase subagents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.state_store import StateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes-file", required=True, type=Path)
    parser.add_argument("--dump-dir", required=True, type=Path)
    parser.add_argument("--schema-file", required=True, type=Path)
    parser.add_argument("--molecules-registry", required=True, type=Path)
    parser.add_argument("--batch-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    args = parser.parse_args(argv)

    routes: list[dict[str, Any]] = json.loads(args.routes_file.read_text(encoding="utf-8"))
    schema: dict[str, Any] = json.loads(args.schema_file.read_text(encoding="utf-8"))
    molecules_raw: dict[str, Any] = json.loads(args.molecules_registry.read_text(encoding="utf-8"))
    molecules = molecules_raw.get("molecules", [])

    fields_by_collection: dict[str, list[str]] = {
        c["name"]: [f["name"] for f in c["fields"]] for c in schema.get("collections", [])
    }
    molecule_names = [m["name"] for m in molecules]

    pages: list[dict[str, Any]] = []
    for r in routes:
        slug = r["slug"]
        html_path = args.dump_dir / f"{slug}.html"
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        collection = r["collection"]
        pages.append(
            {
                "name": slug,
                "route_slug": slug,
                "collection": collection,
                "collection_fields": fields_by_collection.get(collection, []),
                "available_molecules": molecule_names,
                "html_sample": html[:5000],
                "template_type": r.get("template_type", "default"),
                "output_path": f"frontend/pages/{slug}/+Page.tsx",
            }
        )

    args.batch_file.write_text(json.dumps({"pages": pages}, indent=2, ensure_ascii=False))
    store = StateStore(args.state_file)
    store.set("pages_batch_size", len(pages))
    print(f"prepare_pages_batch OK. {len(pages)} pagine in batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
