#!/usr/bin/env python3
"""Detect recurring atomic patterns in WP HTML dumps -> atom_registry.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from lib.state_store import StateStore

ATOM_TAGS = {"button", "input", "a", "select", "textarea", "img", "label"}
NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _pascal_case(parts: list[str]) -> str:
    segments: list[str] = []
    for p in parts:
        for seg in NON_ALNUM.split(p):
            if seg:
                segments.append(seg[0].upper() + seg[1:].lower())
    name = "".join(segments) or "Element"
    return name if name[0].isalpha() else "A" + name


def _signature(tag: Tag) -> str:
    raw = tag.get("class")
    if raw is None:
        raw_classes: list[str] = []
    elif isinstance(raw, str):
        raw_classes = [raw]
    else:
        raw_classes = list(raw)
    classes = tuple(sorted(raw_classes))
    return f"{tag.name}|{','.join(classes)}"


def _name_from_signature(sig: str) -> str:
    tag_name, class_str = sig.split("|", 1)
    parts = [tag_name] + [c for c in class_str.split(",") if c]
    return _pascal_case(parts)


def _element_html(tag: Tag) -> str:
    return str(tag)[:1000]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-dir", required=True, type=Path)
    parser.add_argument("--registry-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--min-occurrences", type=int, default=3)
    args = parser.parse_args(argv)

    signature_counter: Counter[str] = Counter()
    signature_samples: dict[str, str] = {}

    for html_file in args.dump_dir.glob("*.html"):
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        for tag in soup.find_all(ATOM_TAGS):
            if not isinstance(tag, Tag):
                continue
            sig = _signature(tag)
            signature_counter[sig] += 1
            signature_samples.setdefault(sig, _element_html(tag))

    atoms: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for sig, count in signature_counter.items():
        if count < args.min_occurrences:
            continue
        name = _name_from_signature(sig)
        base = name
        i = 2
        while name in seen_names:
            name = f"{base}{i}"
            i += 1
        seen_names.add(name)
        atoms.append(
            {
                "name": name,
                "signature": sig,
                "occurrences": count,
                "sample_html": signature_samples[sig],
                "output_path": f"frontend/src/components/atoms/{name}.tsx",
            }
        )

    registry = {"atoms": atoms}
    args.registry_file.write_text(json.dumps(registry, indent=2, ensure_ascii=False))

    store = StateStore(args.state_file)
    store.set("atoms_batch_size", len(atoms))
    print(f"detect_atoms OK. {len(atoms)} atomi candidati rilevati.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
