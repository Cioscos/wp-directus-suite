#!/usr/bin/env python3
"""Aggregate state files → FRONTEND_REPORT.md."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from lib.state_store import StateStore

SKILL_VERSION = "0.1.0"


def _now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--routes-file", required=True, type=Path)
    parser.add_argument("--forms-file", required=True, type=Path)
    parser.add_argument("--verify-file", required=True, type=Path)
    parser.add_argument("--atoms-registry", required=True, type=Path)
    parser.add_argument("--molecules-registry", required=True, type=Path)
    parser.add_argument("--pages-batch", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--templates-dir", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    args = parser.parse_args(argv)

    state: dict[str, Any] = json.loads(args.state_file.read_text())
    routes: list[dict[str, Any]] = json.loads(args.routes_file.read_text())
    forms: list[dict[str, Any]] = (
        json.loads(args.forms_file.read_text()) if args.forms_file.exists() else []
    )
    verify: dict[str, dict[str, Any]] = (
        json.loads(args.verify_file.read_text()) if args.verify_file.exists() else {}
    )
    atoms = (
        json.loads(args.atoms_registry.read_text()).get("atoms", [])
        if args.atoms_registry.exists()
        else []
    )
    molecules = (
        json.loads(args.molecules_registry.read_text()).get("molecules", [])
        if args.molecules_registry.exists()
        else []
    )
    pages = (
        json.loads(args.pages_batch.read_text()).get("pages", [])
        if args.pages_batch.exists()
        else []
    )

    generated_slugs: set[str] = set()
    for p in pages:
        if (args.output_dir / p["output_path"]).exists():
            generated_slugs.add(p["route_slug"])

    wp_slugs = {r["slug"] for r in routes}
    missing_routes = sorted(wp_slugs - generated_slugs)
    extra_routes = sorted(generated_slugs - wp_slugs)

    routes_coverage = [
        {
            "wp_url": r["url"],
            "react_route": f"/{r['slug']}" if r["slug"] != "index" else "/",
            "generated": r["slug"] in generated_slugs,
        }
        for r in routes
    ]
    coverage_pct = round(100 * len(generated_slugs) / len(routes), 1) if routes else 0

    manual_todos: list[dict[str, str]] = []
    if forms:
        manual_todos.append(
            {
                "category": "Form backend",
                "location": "Vedi sezione 'Form rilevati'",
                "description": "Configura Directus Flow o servizio terzo per i form submit.",
            }
        )

    warnings: list[str] = []
    if state.get("last_fail_rate"):
        warnings.append(f"Alcuni subagent falliti (fail_rate={state['last_fail_rate']:.1%}).")

    env = Environment(loader=FileSystemLoader(str(args.templates_dir)), autoescape=False)
    template = env.get_template("FRONTEND_REPORT.md.j2")
    rendered = template.render(
        generated_at=_now(),
        skill_version=SKILL_VERSION,
        mode=state.get("mode", "n/a"),
        directus_url=state.get("directus_url_hint", "n/a"),
        wp_source=state.get("wp_source_hint", "n/a"),
        i18n_enabled=state.get("i18n_enabled", False),
        i18n_locales=state.get("i18n_locales", []),
        routes_coverage=routes_coverage,
        routes_total=len(routes),
        routes_generated=len(generated_slugs),
        coverage_pct=coverage_pct,
        atoms_count=len(atoms),
        molecules_count=len(molecules),
        pages_count=len(generated_slugs),
        verify_results=verify,
        manual_todos=manual_todos,
        forms=forms,
        missing_routes=missing_routes,
        extra_routes=extra_routes,
        warnings=warnings,
    )
    args.report_file.write_text(rendered, encoding="utf-8")

    store = StateStore(args.state_file)
    store.set("phase", "done")
    print(f"report OK. {args.report_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
