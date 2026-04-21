"""Verify migration: count comparison (WP vs Directus), spot-check.

Output: `state/verify.json`. Exit code 0 if all required-resource deltas are 0,
non-zero otherwise.
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore
from lib.directus_api import DirectusClient
from lib.wp_mysql import MySQLClient
from lib.collections import _pluralize


def wp_counts(mc):
    return {
        "posts": int(mc.query(
            "SELECT COUNT(*) FROM wp_posts WHERE post_type='post' "
            "AND post_status IN ('publish','draft');")[0][0]),
        "pages": int(mc.query(
            "SELECT COUNT(*) FROM wp_posts WHERE post_type='page' "
            "AND post_status IN ('publish','draft');")[0][0]),
        "categories": int(mc.query(
            "SELECT COUNT(*) FROM wp_term_taxonomy WHERE taxonomy='category';"
        )[0][0]),
        "tags": int(mc.query(
            "SELECT COUNT(*) FROM wp_term_taxonomy WHERE taxonomy='post_tag';"
        )[0][0]),
        "media": int(mc.query(
            "SELECT COUNT(*) FROM wp_posts WHERE post_type='attachment';"
        )[0][0]),
        "users": int(mc.query("SELECT COUNT(*) FROM wp_users;")[0][0]),
    }


def directus_count(dc, collection):
    got = dc.get(f"/items/{collection}?aggregate[count]=*")
    if got and len(got) > 0:
        return int(got[0]["count"])
    return 0


def directus_files_count(dc):
    got = dc.get("/files?aggregate[count]=*")
    if got and len(got) > 0:
        return int(got[0]["count"])
    return 0


def spot_check(mc, dc, sample=3):
    rows = mc.query(
        "SELECT ID FROM wp_posts WHERE post_type='post' "
        "AND post_status='publish' ORDER BY ID;"
    )
    ids = [int(r[0]) for r in rows]
    if not ids:
        return []
    picks = random.sample(ids, min(sample, len(ids)))
    results = []
    for wp_id in picks:
        wp_obj = mc.query_json(
            f"SELECT JSON_OBJECT('t', post_title, 'l', CHAR_LENGTH(post_content)) "
            f"FROM wp_posts WHERE ID={wp_id};"
        )
        d = dc.get(f"/items/posts?filter[wp_original_id][_eq]={wp_id}"
                   f"&fields=title,content&limit=1") or []
        if not d:
            results.append({"wp_id": wp_id, "status": "missing"})
            continue
        d_len = len(d[0].get("content") or "")
        results.append({
            "wp_id": wp_id,
            "wp_title": wp_obj.get("t"),
            "directus_title": d[0].get("title"),
            "wp_content_len": int(wp_obj.get("l") or 0),
            "directus_content_len": d_len,
            "match": wp_obj.get("t") == d[0].get("title")
                     and abs(int(wp_obj.get("l") or 0) - d_len) < 10,
        })
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--verify-file", required=True)
    ap.add_argument("--discovery-file", required=True)
    ap.add_argument("--wp-docker-service", default=None)
    args = ap.parse_args()

    mc = MySQLClient(
        host=os.environ.get("WP_DB_HOST", "localhost"),
        port=int(os.environ.get("WP_DB_PORT", "3306")),
        user=os.environ["WP_DB_USER"],
        password=os.environ["WP_DB_PASSWORD"],
        database=os.environ["WP_DB_NAME"],
        docker_service=args.wp_docker_service,
    )
    dc = DirectusClient(os.environ["DIRECTUS_URL"], os.environ["DIRECTUS_ADMIN_TOKEN"])

    wp = wp_counts(mc)
    d = {
        "posts": directus_count(dc, "posts"),
        "pages": directus_count(dc, "pages"),
        "categories": directus_count(dc, "categories"),
        "tags": directus_count(dc, "tags"),
        "media": directus_files_count(dc),
        "authors": directus_count(dc, "authors"),
    }

    discovery = json.loads(Path(args.discovery_file).read_text(encoding="utf-8"))
    for cpt in discovery.get("custom_post_types", []):
        coll = _pluralize(cpt["post_type"])
        d[coll] = directus_count(dc, coll)

    deltas = {}
    for k in ("posts", "pages", "categories", "tags"):
        deltas[k] = d[k] - wp[k]
    deltas["media"] = d["media"] - wp["media"]

    spots = spot_check(mc, dc)

    out = {"wp": wp, "directus": d, "deltas": deltas, "spot_check": spots}
    Path(args.verify_file).write_text(json.dumps(out, indent=2), encoding="utf-8")

    state = StateStore(Path(args.state_file))
    st = state.load()
    st["counts"] = {"wp": wp, "directus": d}
    st["checkpoints"]["verify_done"] = True
    st["phase"] = "report"
    state.save(st)

    print("=== Verify ===")
    for k in sorted(set(list(wp.keys()) + list(d.keys()))):
        w = wp.get(k, "-")
        dd = d.get(k, "-")
        print(f"  {k:15s}  WP:{w}  D:{dd}")
    bad = any(v != 0 for k, v in deltas.items() if k in ("posts", "pages"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
