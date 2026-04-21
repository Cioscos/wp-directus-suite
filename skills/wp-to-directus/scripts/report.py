"""Generate MIGRATION_REPORT.md from state + discovery + verify + mapping files."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore


def _row(k, w, d):
    mark = "OK" if w == d else ("WARN" if abs(w - d) <= 2 else "FAIL")
    return f"| {k} | {w} | {d} | {mark} |"


def render(state, discovery, verify) -> str:
    now = datetime.now(timezone.utc).isoformat()
    wp = verify["wp"]; d = verify["directus"]

    lines = [
        "# WordPress -> Directus Migration Report",
        "",
        f"**Generated:** {now}",
        f"**Mode:** {state.get('mode', 'unknown')}",
        f"**WP site:** {os.environ.get('WP_SITE_URL', '')}",
        f"**Directus:** {os.environ.get('DIRECTUS_URL', '')}",
        "",
        "## Summary",
        "",
        "| Resource | WP | Directus | Status |",
        "|----------|----|----------|--------|",
    ]
    for k in sorted(set(list(wp.keys()) + list(d.keys()))):
        if k not in wp or k not in d:
            continue
        lines.append(_row(k, wp[k], d[k]))

    lines.extend(["", "## Custom Content Migrated", ""])
    cpts = discovery.get("custom_post_types", [])
    if cpts:
        for cpt in cpts:
            lines.append(f"- Custom post_type `{cpt['post_type']}` "
                         f"(WP count: {cpt['count']})")
    else:
        lines.append("- Nessun custom post_type rilevato.")

    taxes = discovery.get("custom_taxonomies", [])
    if taxes:
        lines.append("")
        for t in taxes:
            lines.append(f"- Custom taxonomy `{t}`")

    meta_keys = discovery.get("custom_meta_keys", [])
    if meta_keys:
        lines.append("")
        lines.append("### Custom meta keys (top 10)")
        lines.append("")
        lines.append("| Key | Count |")
        lines.append("|-----|-------|")
        for mk in meta_keys[:10]:
            lines.append(f"| `{mk['key']}` | {mk['count']} |")

    lines.extend(["", "## Plugins Detected", ""])
    plugins = discovery.get("plugins", [])
    if plugins:
        lines.append("| Plugin | Class | Action |")
        lines.append("|--------|-------|--------|")
        actions = {
            "unsupported": "Listed only — manual follow-up required.",
            "partial": "Custom table dumped in `state/plugin_dumps/`; schema not auto-created.",
            "migratable": "Data migrated as custom collection where possible.",
        }
        for p in plugins:
            lines.append(f"| `{p['slug']}` | {p['class']} | {actions.get(p['class'], '-')} |")
    else:
        lines.append("_Nessun plugin attivo rilevato._")

    short = discovery.get("shortcodes") or []
    if short:
        lines.extend(["", "## Shortcodes Detected", ""])
        lines.append("I seguenti post contengono shortcode che richiedono rendering manuale:")
        for s in short:
            codes = ", ".join(f"`[{c}]`" for c in s["shortcodes"])
            lines.append(f"- post_id={s['wp_id']}: {codes}")

    non_core = discovery.get("non_core_tables", [])
    if non_core:
        lines.extend(["", "## Non-Core Tables Ignored", ""])
        for t in non_core:
            lines.append(f"- `{t}`")

    errors = state.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.append("| Phase | Subphase | Context | Error |")
        lines.append("|-------|----------|---------|-------|")
        for e in errors[:100]:
            ctx = e.get("wp_id", "-")
            lines.append(
                f"| {e.get('phase', '-')} | {e.get('subphase', '-')} | "
                f"wp_id={ctx} | {e.get('error', '-')[:80]} |"
            )

    lines.extend([
        "",
        "## Manual Follow-up",
        "",
        "- [ ] Verifica rendering shortcode in frontend Directus",
        "- [ ] Ricrea utenti admin Directus (ruoli WP non migrati)",
        "- [ ] Permalink redirect: mappa WP URLs -> Directus content paths",
        "- [ ] Ripristina meta SEO (Yoast ecc.) manualmente",
        "- [ ] Temi WP non migrabili (frontend da ricostruire)",
        "",
        "## Mappings",
        "",
        "File: `state/mappings.json` — `wp_original_id -> directus_id` per collection, "
        "utilizzabile per rollback manuale o debug.",
        "",
    ])

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--discovery-file", required=True)
    ap.add_argument("--verify-file", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    store = StateStore(Path(args.state_file))
    state = store.load()
    discovery = json.loads(Path(args.discovery_file).read_text(encoding="utf-8"))
    verify = json.loads(Path(args.verify_file).read_text(encoding="utf-8"))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(state, discovery, verify), encoding="utf-8")

    state["checkpoints"]["report_done"] = True
    state["phase"] = "done"
    store.save(state)
    print(f"  + report written to {args.output}")


if __name__ == "__main__":
    main()
