#!/usr/bin/env python3
"""Mark a checkpoint item as done in state.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.state_store import StateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--item", required=True)
    args = parser.parse_args(argv)
    store = StateStore(args.state_file)
    store.mark_done(args.bucket, args.item)
    print(f"marked {args.bucket}/{args.item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
