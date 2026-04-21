"""Migrate content from WordPress (MySQL) to Directus (REST).

Phase-aware, resumable via state.json sub-checkpoints. Each phase rebuilds
in-memory maps from Directus (via wp_original_id) before doing work.

Usage:
  PYTHONUNBUFFERED=1 python scripts/migrate.py \
      --state-file state/.state.json \
      --mapping-file state/mappings.json \
      --discovery-file state/discovery.json \
      [--wp-docker-service wordpress_db]
"""

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore
from lib.directus_api import DirectusClient
from lib.wp_mysql import MySQLClient
from lib.mapping import MappingStore
from lib.collections import _pluralize

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _rebuild_map(dc: DirectusClient, ms: MappingStore, collection: str) -> None:
    for item in dc.list_all(collection):
        if item.get("wp_original_id"):
            ms.put(collection, int(item["wp_original_id"]), item["id"])


def migrate_authors(dc, mc, ms, state):
    if state.load()["migrate_subphase"]["authors_done"]:
        print("=== Authors: skip (done) ==="); return
    print("=== Authors ===")
    _rebuild_map(dc, ms, "authors")
    rows = mc.query("SELECT ID, user_login, user_email, display_name FROM wp_users;")
    for row in rows:
        wp_id = int(row[0])
        if ms.get("authors", wp_id):
            continue
        d = dc.post("/items/authors", {
            "name": row[3], "email": row[2], "slug": row[1],
            "wp_original_id": wp_id,
        })
        if d:
            ms.put("authors", wp_id, d["id"])
            print(f"  + {row[3]} (WP:{wp_id} -> D:{d['id']})")
    st = state.load()
    st["migrate_subphase"]["authors_done"] = True
    state.save(st)


def migrate_taxonomy(dc, mc, ms, state, taxonomy, collection, subphase_key):
    if state.load()["migrate_subphase"].get(subphase_key):
        print(f"=== {collection}: skip (done) ==="); return
    print(f"=== {collection} ===")
    _rebuild_map(dc, ms, collection)
    sql = f"""SELECT t.term_id, t.name, t.slug, IFNULL(tt.description,'')
    FROM wp_terms t JOIN wp_term_taxonomy tt ON t.term_id = tt.term_id
    WHERE tt.taxonomy = '{taxonomy}';"""
    rows = mc.query(sql)
    for row in rows:
        wp_id = int(row[0])
        if ms.get(collection, wp_id):
            continue
        data = {"name": row[1], "slug": row[2], "wp_original_id": wp_id}
        if len(row) > 3 and row[3]:
            data["description"] = row[3]
        d = dc.post(f"/items/{collection}", data)
        if d:
            ms.put(collection, wp_id, d["id"])
            print(f"  + {row[1]} (WP:{wp_id} -> D:{d['id']})")
    st = state.load()
    st["migrate_subphase"][subphase_key] = True
    state.save(st)


def migrate_media(dc, mc, state):
    st = state.load()
    print("=== Media ===")
    wp_host = os.environ.get("WP_SITE_URL", "")
    wp_internal = os.environ.get("WP_INTERNAL_URL", "")

    # rebuild file title -> uuid
    files = dc.get("/files?fields=id,title&limit=-1") or []
    titles = {f["title"]: f["id"] for f in files if f.get("title")}

    rows = mc.query(
        "SELECT ID, post_title, guid, post_mime_type FROM wp_posts "
        "WHERE post_type='attachment' ORDER BY ID;"
    )
    done_count = st["migrate_subphase"]["media_done_count"]
    new_count = 0
    for i, row in enumerate(rows):
        wp_id = int(row[0])
        title = row[1]
        if title in titles:
            continue
        if i < done_count:
            continue
        url = row[2]
        if wp_host and wp_internal:
            url = url.replace(wp_host, wp_internal)
        try:
            d = dc.post("/files/import", {"url": url, "data": {"title": title}})
            if d:
                titles[title] = d["id"]
                new_count += 1
                print(f"  + {title} (WP:{wp_id} -> D:{d['id']})")
        except RuntimeError as e:
            state.append_error(phase="migrate", subphase="media",
                               wp_id=wp_id, error=str(e)[:200], retries=3)
            print(f"  X {title} (WP:{wp_id}) FAILED: {str(e)[:80]}")
        st2 = state.load()
        st2["migrate_subphase"]["media_done_count"] = i + 1
        state.save(st2)
    print(f"  = {new_count} imported, {len(titles)} total in Directus")


def _meta_value(mc, post_id, key):
    rows = mc.query(
        f"SELECT meta_value FROM wp_postmeta WHERE post_id={post_id} "
        f"AND meta_key='{key}' LIMIT 1;"
    )
    return rows[0][0] if rows else None


def migrate_posts(dc, mc, ms, state):
    print("=== Posts ===")
    _rebuild_map(dc, ms, "posts")
    _rebuild_map(dc, ms, "authors")

    files = dc.get("/files?fields=id,title&limit=-1") or []
    titles = {f["title"]: f["id"] for f in files if f.get("title")}

    rows = mc.query(
        "SELECT ID, post_author, post_date, post_title, post_name, "
        "post_status, post_modified FROM wp_posts "
        "WHERE post_type='post' AND post_status IN ('publish','draft') "
        "ORDER BY ID;"
    )

    st = state.load()
    done = st["migrate_subphase"]["posts_done_count"]

    for i, row in enumerate(rows):
        wp_id = int(row[0])
        if ms.get("posts", wp_id):
            continue
        if i < done:
            continue

        content = mc.query_json(
            f"SELECT JSON_OBJECT('c', post_content, 'e', post_excerpt) "
            f"FROM wp_posts WHERE ID={wp_id};"
        )
        status = "published" if row[5] == "publish" else "draft"
        author_id = ms.get("authors", int(row[1]))

        thumb = _meta_value(mc, wp_id, "_thumbnail_id")
        featured = None
        if thumb:
            t_rows = mc.query(
                f"SELECT post_title FROM wp_posts WHERE ID={int(thumb)};"
            )
            if t_rows and t_rows[0][0] in titles:
                featured = titles[t_rows[0][0]]

        data = {
            "title": row[3], "slug": row[4],
            "content": content.get("c", "") or "",
            "excerpt": content.get("e") or None,
            "status": status,
            "published_date": row[2],
            "modified_date": row[6],
            "author": author_id,
            "wp_original_id": wp_id,
        }
        if featured:
            data["featured_image"] = featured

        extra = {}
        for key in ("source_url", "reading_time", "difficulty_level", "is_featured"):
            v = _meta_value(mc, wp_id, key)
            if v is not None:
                extra[key] = v
        if extra:
            data["extra_meta"] = extra

        try:
            d = dc.post("/items/posts", data)
            if d:
                ms.put("posts", wp_id, d["id"])
                print(f"  + {row[3]} (WP:{wp_id} -> D:{d['id']}) [{status}]")
        except RuntimeError as e:
            state.append_error(phase="migrate", subphase="posts",
                               wp_id=wp_id, error=str(e)[:200], retries=3)
            print(f"  X {row[3]} (WP:{wp_id}) FAILED: {str(e)[:80]}")

        st2 = state.load()
        st2["migrate_subphase"]["posts_done_count"] = i + 1
        state.save(st2)


def migrate_pages(dc, mc, ms, state):
    print("=== Pages ===")
    _rebuild_map(dc, ms, "pages")
    _rebuild_map(dc, ms, "authors")

    rows = mc.query(
        "SELECT ID, post_author, post_date, post_title, post_name, "
        "post_status, menu_order, post_parent FROM wp_posts "
        "WHERE post_type='page' AND post_status IN ('publish','draft') "
        "ORDER BY ID;"
    )

    parents = {}
    st = state.load()
    done = st["migrate_subphase"]["pages_done_count"]

    for i, row in enumerate(rows):
        wp_id = int(row[0])
        parents[wp_id] = int(row[7]) if row[7] else 0
        if ms.get("pages", wp_id):
            continue
        if i < done:
            continue
        content = mc.query_json(
            f"SELECT JSON_OBJECT('c', post_content) FROM wp_posts WHERE ID={wp_id};"
        )
        status = "published" if row[5] == "publish" else "draft"
        data = {
            "title": row[3], "slug": row[4],
            "content": content.get("c", "") or "",
            "status": status, "published_date": row[2],
            "author": ms.get("authors", int(row[1])),
            "menu_order": int(row[6]) if row[6] else 0,
            "wp_original_id": wp_id,
        }
        try:
            d = dc.post("/items/pages", data)
            if d:
                ms.put("pages", wp_id, d["id"])
                print(f"  + {row[3]} (WP:{wp_id} -> D:{d['id']}) [{status}]")
        except RuntimeError as e:
            state.append_error(phase="migrate", subphase="pages",
                               wp_id=wp_id, error=str(e)[:200], retries=3)

        st2 = state.load()
        st2["migrate_subphase"]["pages_done_count"] = i + 1
        state.save(st2)

    # parent pass
    print("  -- parent references --")
    for wp_id, wp_parent in parents.items():
        if wp_parent > 0:
            d_page = ms.get("pages", wp_id)
            d_parent = ms.get("pages", wp_parent)
            if d_page and d_parent:
                try:
                    dc.patch(f"/items/pages/{d_page}", {"parent_page": d_parent})
                    print(f"  + Page D:{d_page} -> Parent D:{d_parent}")
                except RuntimeError as e:
                    state.append_error(phase="migrate", subphase="pages_parents",
                                       wp_id=wp_id, error=str(e)[:200], retries=3)


def migrate_custom_post_types(dc, mc, ms, state, discovery):
    print("=== Custom post_types ===")
    st = state.load()
    done_list = set(st["migrate_subphase"]["custom_types_done"])
    for cpt in discovery.get("custom_post_types", []):
        post_type = cpt["post_type"]
        if post_type in done_list:
            continue
        collection = _pluralize(post_type)
        _rebuild_map(dc, ms, collection)
        rows = mc.query(
            "SELECT ID, post_author, post_date, post_title, post_name, post_status "
            f"FROM wp_posts WHERE post_type='{post_type}' "
            f"AND post_status IN ('publish','draft') ORDER BY ID;"
        )
        for row in rows:
            wp_id = int(row[0])
            if ms.get(collection, wp_id):
                continue
            content = mc.query_json(
                f"SELECT JSON_OBJECT('c', post_content) FROM wp_posts WHERE ID={wp_id};"
            )
            data = {
                "title": row[3], "slug": row[4],
                "content": content.get("c", "") or "",
                "status": "published" if row[5] == "publish" else "draft",
                "published_date": row[2],
                "author": ms.get("authors", int(row[1])),
                "wp_original_id": wp_id,
            }
            try:
                d = dc.post(f"/items/{collection}", data)
                if d:
                    ms.put(collection, wp_id, d["id"])
                    print(f"  + [{collection}] {row[3]} WP:{wp_id} -> D:{d['id']}")
            except RuntimeError as e:
                state.append_error(phase="migrate", subphase=f"custom:{post_type}",
                                   wp_id=wp_id, error=str(e)[:200], retries=3)
        done_list.add(post_type)
        st2 = state.load()
        st2["migrate_subphase"]["custom_types_done"] = sorted(done_list)
        state.save(st2)


def _junction_exists(dc, junction, parent_id, related_id, parent_field, related_field):
    q = (f"/items/{junction}"
         f"?filter[{parent_field}][_eq]={parent_id}"
         f"&filter[{related_field}][_eq]={related_id}&limit=1")
    got = dc.get(q) or []
    return len(got) > 0


def migrate_relationships(dc, mc, ms, state, discovery):
    if state.load()["migrate_subphase"]["relationships_done"]:
        print("=== Relationships: skip (done) ==="); return
    print("=== Post-Category ===")
    rows = mc.query(
        "SELECT tr.object_id, tt.term_id FROM wp_term_relationships tr "
        "JOIN wp_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id "
        "WHERE tt.taxonomy='category' AND tr.object_id IN "
        "(SELECT ID FROM wp_posts WHERE post_type='post' "
        "AND post_status IN ('publish','draft'));"
    )
    for r in rows:
        dp = ms.get("posts", int(r[0]))
        dc_ = ms.get("categories", int(r[1]))
        if dp and dc_ and not _junction_exists(dc, "posts_categories", dp, dc_,
                                               "posts_id", "categories_id"):
            dc.post("/items/posts_categories",
                    {"posts_id": dp, "categories_id": dc_})
            print(f"  + Post D:{dp} -> Cat D:{dc_}")

    print("=== Post-Tag ===")
    rows = mc.query(
        "SELECT tr.object_id, tt.term_id FROM wp_term_relationships tr "
        "JOIN wp_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id "
        "WHERE tt.taxonomy='post_tag' AND tr.object_id IN "
        "(SELECT ID FROM wp_posts WHERE post_type='post' "
        "AND post_status IN ('publish','draft'));"
    )
    for r in rows:
        dp = ms.get("posts", int(r[0]))
        dt = ms.get("tags", int(r[1]))
        if dp and dt and not _junction_exists(dc, "posts_tags", dp, dt,
                                              "posts_id", "tags_id"):
            dc.post("/items/posts_tags", {"posts_id": dp, "tags_id": dt})
            print(f"  + Post D:{dp} -> Tag D:{dt}")

    # custom taxonomies junctions
    for tax in discovery.get("custom_taxonomies", []):
        coll = _pluralize(tax)
        _rebuild_map(dc, ms, coll)
        junction = f"posts_{coll}"
        rows = mc.query(
            "SELECT tr.object_id, tt.term_id FROM wp_term_relationships tr "
            "JOIN wp_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id "
            f"WHERE tt.taxonomy='{tax}';"
        )
        for r in rows:
            dp = ms.get("posts", int(r[0]))
            dx = ms.get(coll, int(r[1]))
            if dp and dx and not _junction_exists(
                dc, junction, dp, dx, "posts_id", f"{coll}_id"
            ):
                dc.post(f"/items/{junction}",
                        {"posts_id": dp, f"{coll}_id": dx})
                print(f"  + Post D:{dp} -> {coll} D:{dx}")

    st = state.load()
    st["migrate_subphase"]["relationships_done"] = True
    st["checkpoints"]["migrate_done"] = True
    st["phase"] = "verify"
    state.save(st)
    print("  + relationships_done, phase=verify")


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--mapping-file", required=True)
    ap.add_argument("--discovery-file", required=True)
    ap.add_argument("--wp-docker-service", default=None)
    return ap


def _clients(args):
    mc = MySQLClient(
        host=os.environ.get("WP_DB_HOST", "localhost"),
        port=int(os.environ.get("WP_DB_PORT", "3306")),
        user=os.environ["WP_DB_USER"],
        password=os.environ["WP_DB_PASSWORD"],
        database=os.environ["WP_DB_NAME"],
        docker_service=args.wp_docker_service,
    )
    dc = DirectusClient(os.environ["DIRECTUS_URL"], os.environ["DIRECTUS_ADMIN_TOKEN"])
    return mc, dc


def main():
    args = build_parser().parse_args()
    state = StateStore(Path(args.state_file))
    ms = MappingStore(Path(args.mapping_file))
    mc, dc = _clients(args)

    migrate_authors(dc, mc, ms, state)
    migrate_taxonomy(dc, mc, ms, state, "category", "categories", "categories_done")
    migrate_taxonomy(dc, mc, ms, state, "post_tag", "tags", "tags_done")
    migrate_media(dc, mc, state)
    migrate_posts(dc, mc, ms, state)
    migrate_pages(dc, mc, ms, state)

    import json
    discovery = json.loads(Path(args.discovery_file).read_text(encoding="utf-8"))
    migrate_custom_post_types(dc, mc, ms, state, discovery)
    migrate_relationships(dc, mc, ms, state, discovery)


if __name__ == "__main__":
    main()
