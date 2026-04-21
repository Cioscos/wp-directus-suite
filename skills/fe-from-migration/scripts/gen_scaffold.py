#!/usr/bin/env python3
"""Render Jinja2 templates -> ./frontend/ scaffold."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from lib.state_store import StateStore


def _detect_locales(routes: list[dict[str, Any]]) -> tuple[list[str], str]:
    locales: set[str] = set()
    for r in routes:
        md = r.get("metadata") or {}
        lang = md.get("language") if isinstance(md, dict) else None
        if isinstance(lang, str):
            locales.add(lang)
    if not locales:
        return [], "it"
    sorted_locales = sorted(locales)
    return sorted_locales, sorted_locales[0]


def _render_all(
    env: Environment,
    templates_dir: Path,
    output_dir: Path,
    ctx: dict[str, Any],
) -> None:
    for tpl_path in templates_dir.rglob("*.j2"):
        rel = tpl_path.relative_to(templates_dir)
        output_rel = rel.with_suffix("")
        out_path = output_dir / output_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(str(rel).replace("\\", "/"))
        rendered = template.render(**ctx)
        out_path.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--tokens-file", required=True, type=Path)
    parser.add_argument("--schema-file", required=True, type=Path)
    parser.add_argument("--routes-file", required=True, type=Path)
    parser.add_argument("--global-css", required=True, type=Path)
    parser.add_argument("--templates-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--project-name", default="fe-from-migration-output")
    parser.add_argument("--directus-url", default="http://localhost:8055")
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        print(
            f"ERRORE: {output_dir} non vuota. Usa --force per sovrascrivere.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if output_dir.exists() and args.force:
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    output_dir.mkdir(parents=True, exist_ok=True)

    tokens_file: Path = args.tokens_file
    schema_file: Path = args.schema_file
    routes_file: Path = args.routes_file
    global_css_path: Path = args.global_css

    tokens: dict[str, Any] = json.loads(tokens_file.read_text(encoding="utf-8"))
    schema: dict[str, Any] = json.loads(schema_file.read_text(encoding="utf-8"))
    routes: list[dict[str, Any]] = json.loads(routes_file.read_text(encoding="utf-8"))
    global_css = global_css_path.read_text(encoding="utf-8") if global_css_path.exists() else ""

    locales, default_locale = _detect_locales(routes)

    env = Environment(
        loader=FileSystemLoader(str(args.templates_dir)),
        autoescape=select_autoescape(default_for_string=False),
        keep_trailing_newline=True,
    )

    theme = tokens.get("theme", {})
    tailwind_extend = theme.get("extend", {}) if isinstance(theme, dict) else {}

    ctx: dict[str, Any] = {
        "project_name": args.project_name,
        "directus_url": args.directus_url,
        "tailwind_extend": tailwind_extend,
        "collections": schema.get("collections", []),
        "global_css": global_css,
        "locales": locales,
        "default_locale": default_locale,
        "has_i18n": bool(locales),
    }

    _render_all(env, args.templates_dir, output_dir, ctx)

    store = StateStore(args.state_file)
    store.set("phase", "gen_atoms")
    print(f"gen_scaffold OK. Frontend scaffolded in {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
