#!/usr/bin/env python3
"""Analyze CSS dumps -> Tailwind tokens + global.css."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from lib.state_store import StateStore
from lib.style_extractor import StyleExtractor

FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.DOTALL)
RESET_RULES = re.compile(r"(?:\*|html|body|:root)\s*\{[^}]*\}", re.DOTALL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--dump-dir", required=True, type=Path)
    parser.add_argument("--tokens-file", required=True, type=Path)
    parser.add_argument("--global-css", required=True, type=Path)
    args = parser.parse_args(argv)

    css_parts: list[str] = []
    for css_file in sorted(args.dump_dir.glob("*.css")):
        css_parts.append(css_file.read_text(encoding="utf-8"))
    combined = "\n".join(css_parts)

    if not combined.strip():
        print("ERRORE: nessun CSS trovato in state/wp_dump/", file=sys.stderr)
        return 1

    ex = StyleExtractor()
    theme = ex.build_tailwind_theme(combined)
    args.tokens_file.write_text(
        json.dumps(theme, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    global_parts: list[str] = []
    for m in FONT_FACE_RE.finditer(combined):
        global_parts.append(m.group(0))
    for m in RESET_RULES.finditer(combined):
        global_parts.append(m.group(0))
    args.global_css.write_text("\n\n".join(global_parts), encoding="utf-8")

    store = StateStore(args.state_file)
    store.set("phase", "introspect_directus")
    colors = theme["theme"]["extend"]["colors"]
    print(f"analyze_style OK. Tokens estratti: {len(colors)} colori.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
