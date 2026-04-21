#!/usr/bin/env python3
"""Verify LLM-generated files exist + advance phase if success threshold met."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.state_store import StateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--registry-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--next-phase", required=True)
    parser.add_argument("--fail-threshold", type=float, default=0.2)
    args = parser.parse_args(argv)

    registry: dict[str, Any] = json.loads(args.registry_file.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = (
        registry.get("atoms") or registry.get("molecules") or registry.get("pages") or []
    )
    if not items:
        print("WARN: registry vuota, skip verifica.", file=sys.stderr)
        store = StateStore(args.state_file)
        store.set("phase", args.next_phase)
        return 0

    missing: list[str] = []
    for item in items:
        out_path = args.output_dir / item["output_path"]
        if not out_path.exists():
            missing.append(item["name"])

    fail_rate = len(missing) / len(items)
    print(
        f"verify_generated: {len(items) - len(missing)}/{len(items)} OK, fail_rate={fail_rate:.2%}"
    )

    if missing:
        print("Mancanti: " + ", ".join(missing), file=sys.stderr)

    if fail_rate > args.fail_threshold:
        print(
            f"ERRORE: fail_rate {fail_rate:.2%} supera soglia {args.fail_threshold:.2%}.",
            file=sys.stderr,
        )
        return 1

    store = StateStore(args.state_file)
    store.set("phase", args.next_phase)
    store.set("last_fail_rate", fail_rate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
