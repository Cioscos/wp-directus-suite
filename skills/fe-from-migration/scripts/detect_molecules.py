#!/usr/bin/env python3
"""Detect molecule patterns (containers aggregating >=2 atoms)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from lib.state_store import StateStore

MOLECULE_CONTAINERS = {"header", "footer", "nav", "section", "article", "aside", "form"}
NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _pascal_case(parts: list[str]) -> str:
    segs: list[str] = []
    for p in parts:
        for s in NON_ALNUM.split(p):
            if s:
                segs.append(s[0].upper() + s[1:].lower())
    name = "".join(segs) or "Molecule"
    return name if name[0].isalpha() else "M" + name


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


def _contains_atom(tag: Tag, atom_sigs: set[str]) -> bool:
    for descendant in tag.find_all(True):
        if isinstance(descendant, Tag) and _signature(descendant) in atom_sigs:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-dir", required=True, type=Path)
    parser.add_argument("--atoms-registry", required=True, type=Path)
    parser.add_argument("--registry-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--min-occurrences", type=int, default=2)
    args = parser.parse_args(argv)

    atoms = json.loads(args.atoms_registry.read_text(encoding="utf-8")).get("atoms", [])
    atom_sigs = {a["signature"] for a in atoms}

    counter: Counter[str] = Counter()
    samples: dict[str, str] = {}

    for html_file in args.dump_dir.glob("*.html"):
        soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
        for tag in soup.find_all(MOLECULE_CONTAINERS):
            if not isinstance(tag, Tag):
                continue
            if not _contains_atom(tag, atom_sigs):
                continue
            sig = _signature(tag)
            counter[sig] += 1
            samples.setdefault(sig, str(tag)[:3000])

    molecules: list[dict[str, object]] = []
    seen: set[str] = set()
    for sig, count in counter.items():
        if count < args.min_occurrences:
            continue
        name = _pascal_case([sig.split("|")[0], *sig.split("|")[1].split(",")])
        base = name
        i = 2
        while name in seen:
            name = f"{base}{i}"
            i += 1
        seen.add(name)
        molecules.append(
            {
                "name": name,
                "signature": sig,
                "occurrences": count,
                "sample_html": samples[sig],
                "output_path": f"frontend/src/components/molecules/{name}.tsx",
            }
        )

    args.registry_file.write_text(
        json.dumps({"molecules": molecules}, indent=2, ensure_ascii=False)
    )
    store = StateStore(args.state_file)
    store.set("molecules_batch_size", len(molecules))
    print(f"detect_molecules OK. {len(molecules)} molecole candidate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
