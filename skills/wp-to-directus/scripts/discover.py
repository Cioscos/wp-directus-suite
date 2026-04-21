"""Scan WordPress for plugins, custom post_types, custom taxonomies,
unknown meta_keys, and non-core tables.

Writes `state/discovery.json` and marks `checkpoints.discovery_done`.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore
from lib.wp_mysql import MySQLClient
from lib.php_serialized import parse_serialized_array


CORE_TABLES = {
    "wp_posts", "wp_postmeta", "wp_users", "wp_usermeta", "wp_options",
    "wp_terms", "wp_term_taxonomy", "wp_term_relationships", "wp_termmeta",
    "wp_comments", "wp_commentmeta", "wp_links",
}

UNSUPPORTED_HINTS = [
    "yoast", "wordfence", "w3-total-cache", "wp-super-cache", "akismet",
    "contact-form-7", "elementor", "woocommerce", "all-in-one-seo",
    "rankmath", "advanced-custom-fields", "acf",
]

SHORTCODE_RE = re.compile(r"\[([a-z0-9_-]+)(\s[^\]]*)?\]", re.IGNORECASE)


def classify_plugin(plugin_slug: str, custom_tables: list) -> str:
    slug_lower = plugin_slug.lower()
    if any(h in slug_lower for h in UNSUPPORTED_HINTS):
        return "unsupported"
    slug_root = plugin_slug.split("/")[0]
    # Try common prefix conventions: hyphen→underscore, or stripped separators.
    variants = {
        slug_root.replace("-", "_"),
        slug_root.replace("-", ""),
        slug_root.replace("_", ""),
    }
    for v in variants:
        if not v:
            continue
        prefix = f"wp_{v}"
        if any(t.startswith(prefix) for t in custom_tables):
            return "partial"
    return "migratable"


def scan_plugins(mc: MySQLClient) -> list:
    rows = mc.query(
        "SELECT option_value FROM wp_options WHERE option_name='active_plugins';"
    )
    if not rows:
        return []
    raw = rows[0][0] if rows[0] else ""
    return parse_serialized_array(raw)


def scan_custom_post_types(mc: MySQLClient) -> list:
    rows = mc.query(
        "SELECT DISTINCT post_type, COUNT(*) FROM wp_posts "
        "WHERE post_type NOT IN ('post','page','attachment','revision','nav_menu_item') "
        "GROUP BY post_type;"
    )
    return [{"post_type": r[0], "count": int(r[1])} for r in rows]


def scan_custom_taxonomies(mc: MySQLClient) -> list:
    rows = mc.query(
        "SELECT DISTINCT taxonomy FROM wp_term_taxonomy "
        "WHERE taxonomy NOT IN ('category','post_tag','nav_menu');"
    )
    return [r[0] for r in rows]


def scan_meta_keys(mc: MySQLClient) -> list:
    rows = mc.query(
        "SELECT meta_key, COUNT(*) FROM wp_postmeta "
        "WHERE meta_key NOT LIKE '|_%' ESCAPE '|' "
        "GROUP BY meta_key ORDER BY COUNT(*) DESC LIMIT 100;"
    )
    return [{"key": r[0], "count": int(r[1])} for r in rows]


def scan_non_core_tables(mc: MySQLClient) -> list:
    # SHOW TABLES LIKE does not accept ESCAPE; use doubled backslash so the
    # MySQL string literal yields `\_`, which LIKE treats as a literal `_`.
    rows = mc.query(r"SHOW TABLES LIKE 'wp\\_%';")
    return sorted(r[0] for r in rows if r and r[0] not in CORE_TABLES)


def scan_shortcodes_in_posts(mc: MySQLClient) -> list:
    rows = mc.query(
        "SELECT ID FROM wp_posts "
        "WHERE post_type IN ('post','page') AND post_status='publish';"
    )
    hits = []
    for r in rows:
        wp_id = int(r[0])
        obj = mc.query_json(
            f"SELECT JSON_OBJECT('c', post_content) FROM wp_posts WHERE ID={wp_id};"
        )
        content = obj.get("c", "") or ""
        codes = {m.group(1) for m in SHORTCODE_RE.finditer(content)}
        if codes:
            hits.append({"wp_id": wp_id, "shortcodes": sorted(codes)})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--discovery-file", required=True)
    ap.add_argument("--wp-docker-service", default=None,
                    help="Docker Compose service name (test mode only)")
    args = ap.parse_args()

    state = StateStore(Path(args.state_file))
    st = state.load()

    import os
    mc = MySQLClient(
        host=os.environ.get("WP_DB_HOST", "localhost"),
        port=int(os.environ.get("WP_DB_PORT", "3306")),
        user=os.environ["WP_DB_USER"],
        password=os.environ["WP_DB_PASSWORD"],
        database=os.environ["WP_DB_NAME"],
        docker_service=args.wp_docker_service,
    )

    non_core = scan_non_core_tables(mc)
    plugin_slugs = scan_plugins(mc)
    plugins = [{"slug": p, "class": classify_plugin(p, non_core)} for p in plugin_slugs]

    custom_post_types = scan_custom_post_types(mc)
    custom_taxonomies = scan_custom_taxonomies(mc)
    meta_keys = scan_meta_keys(mc)
    shortcode_hits = scan_shortcodes_in_posts(mc)

    discovery = {
        "plugins": plugins,
        "custom_post_types": custom_post_types,
        "custom_taxonomies": custom_taxonomies,
        "custom_meta_keys": meta_keys,
        "non_core_tables": non_core,
        "shortcodes": shortcode_hits,
    }

    Path(args.discovery_file).parent.mkdir(parents=True, exist_ok=True)
    Path(args.discovery_file).write_text(
        json.dumps(discovery, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    st["discovery"] = {k: discovery[k] for k in [
        "plugins", "custom_post_types", "custom_taxonomies",
        "custom_meta_keys", "non_core_tables",
    ]}
    st["checkpoints"]["discovery_done"] = True
    st["phase"] = "schema"
    state.save(st)

    print(f"  + discovered: {len(plugin_slugs)} plugins, "
          f"{len(custom_post_types)} custom post_types, "
          f"{len(custom_taxonomies)} custom taxonomies, "
          f"{len(meta_keys)} meta_keys, "
          f"{len(non_core)} non-core tables, "
          f"{len(shortcode_hits)} posts with shortcodes")


if __name__ == "__main__":
    main()
