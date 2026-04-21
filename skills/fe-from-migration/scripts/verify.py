#!/usr/bin/env python3
"""Run npm install + tsc + eslint + vite build on ./frontend/."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from lib.state_store import StateStore

COMMANDS: list[tuple[str, list[str]]] = [
    ("npm_install", ["npm", "install", "--no-audit", "--no-fund"]),
    ("tsc", ["npx", "tsc", "--noEmit"]),
    ("eslint", ["npx", "eslint", ".", "--ext", ".ts,.tsx", "--max-warnings", "0"]),
    ("build", ["npx", "vike", "build"]),
]


def _run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "exit": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--verify-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    results: dict[str, dict[str, Any]] = {}
    overall_ok = True

    for key, cmd in COMMANDS:
        result = _run(cmd, cwd=args.output_dir)
        results[key] = result
        print(f"verify {key}: exit={result['exit']}")
        if result["exit"] != 0:
            overall_ok = False
            break

    args.verify_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    store = StateStore(args.state_file)
    if overall_ok:
        store.set("phase", "report")
        print("verify OK. Passo a report.")
        return 0

    print(
        "ERRORE: verify fallito. Phase resta `verify`. Fix errori e re-invoca skill.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
