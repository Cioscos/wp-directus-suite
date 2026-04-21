"""Create Directus collections, fields, and relations for the migration.

Idempotent: checks existence via GET /collections/<name> before POST.
Writes `checkpoints.schema_done = True` on success.
"""

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.directus_api import DirectusClient
from lib.state import StateStore
from lib.collections import (
    authors_def, categories_def, tags_def, posts_def, pages_def,
    junction_def, custom_post_type_def, custom_taxonomy_def, _pluralize,
)


def _exists(dc: DirectusClient, collection: str) -> bool:
    try:
        raw = dc._request("GET", f"/collections/{collection}")
        return True
    except RuntimeError as e:
        if "HTTP 403" in str(e) or "HTTP 404" in str(e):
            return False
        raise


def ensure_collection(dc: DirectusClient, defn: dict) -> None:
    name = defn["collection"]
    if _exists(dc, name):
        print(f"  ~ {name} exists")
        return
    dc.post("/collections", defn)
    print(f"  + {name}")


def add_m2m(dc: DirectusClient, parent: str, related: str) -> None:
    junction = f"{parent}_{related}"
    alias_field = related
    # Alias field on parent
    try:
        dc.post(f"/fields/{parent}", {
            "field": alias_field, "type": "alias",
            "meta": {"interface": "list-m2m", "special": ["m2m"],
                     "options": {"enableCreate": False}},
        })
    except RuntimeError as e:
        if "already exists" not in str(e) and "HTTP 400" not in str(e):
            raise
    # Relations
    for field_name, target, one_field in (
        (f"{parent}_id", parent, alias_field),
        (f"{related}_id", related, None),
    ):
        try:
            dc.post("/relations", {
                "collection": junction, "field": field_name,
                "related_collection": target,
                "meta": {"one_field": one_field, "sort_field": None,
                         "one_deselect_action": "nullify"},
                "schema": {"on_delete": "SET NULL"},
            })
        except RuntimeError as e:
            if "already exists" not in str(e) and "HTTP 400" not in str(e):
                raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--discovery-file", required=True)
    args = ap.parse_args()

    state = StateStore(Path(args.state_file))
    st = state.load()

    dc = DirectusClient(os.environ["DIRECTUS_URL"], os.environ["DIRECTUS_ADMIN_TOKEN"])

    print("=== Core collections ===")
    for defn in (authors_def(), categories_def(), tags_def(),
                 posts_def(), pages_def()):
        ensure_collection(dc, defn)

    print("=== Core junctions ===")
    for parent, related in (("posts", "categories"), ("posts", "tags")):
        ensure_collection(dc, junction_def(parent, related))
        add_m2m(dc, parent, related)

    # Custom post_types
    discovery = json.loads(Path(args.discovery_file).read_text(encoding="utf-8"))
    print("=== Custom post_types ===")
    for cpt in discovery.get("custom_post_types", []):
        ensure_collection(dc, custom_post_type_def(cpt["post_type"]))

    # Custom taxonomies + junctions to posts
    print("=== Custom taxonomies ===")
    for tax in discovery.get("custom_taxonomies", []):
        ensure_collection(dc, custom_taxonomy_def(tax))
        tax_coll = _pluralize(tax)
        ensure_collection(dc, junction_def("posts", tax_coll))
        add_m2m(dc, "posts", tax_coll)

    st["checkpoints"]["schema_done"] = True
    st["phase"] = "migrate"
    state.save(st)
    print("  + schema_done")


if __name__ == "__main__":
    main()
