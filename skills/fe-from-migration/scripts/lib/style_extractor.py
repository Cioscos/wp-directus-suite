"""CSS parser + design tokens extractor."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import cssutils  # type: ignore[import-untyped]

cssutils.log.setLevel("CRITICAL")  # silence parse warnings

HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
RGB_COLOR_RE = re.compile(r"rgba?\(([^)]+)\)")


class StyleExtractor:
    def extract_colors(self, css: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for match in HEX_COLOR_RE.finditer(css):
            hex_val = "#" + match.group(1).lower()
            counter[hex_val] += 1
        for match in RGB_COLOR_RE.finditer(css):
            counter[f"rgb({match.group(1).strip()})"] += 1
        return dict(counter)

    def top_colors(self, css: str, n: int = 8) -> list[str]:
        freq = self.extract_colors(css)
        return [c for c, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]

    def extract_font_families(self, css: str) -> list[str]:
        sheet = cssutils.parseString(css)
        fonts: list[str] = []
        for rule in sheet:
            if rule.type == rule.STYLE_RULE:
                for prop in rule.style:
                    if prop.name in ("font-family", "font"):
                        fonts.append(prop.value.strip())
        seen: set[str] = set()
        deduped: list[str] = []
        for f in fonts:
            if f not in seen:
                seen.add(f)
                deduped.append(f)
        return deduped

    def build_tailwind_theme(self, css: str) -> dict[str, Any]:
        top = self.top_colors(css)
        fonts = self.extract_font_families(css)
        palette = {f"c{i}": c for i, c in enumerate(top)}
        first_font = fonts[0].split(",")[0].strip("\"' ") if fonts else "sans-serif"
        return {
            "theme": {
                "extend": {
                    "colors": palette,
                    "fontFamily": {"sans": [first_font, "sans-serif"]},
                }
            }
        }
