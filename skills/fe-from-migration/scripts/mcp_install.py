#!/usr/bin/env python3
"""Write .mcp.json with directus-postgres MCP server (merge-safe)."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from lib.env_loader import load_dotenv
from lib.state_store import StateStore

DIRECTUS_DB_KEYS = [
    "DIRECTUS_DB_HOST",
    "DIRECTUS_DB_PORT",
    "DIRECTUS_DB_NAME",
    "DIRECTUS_DB_USER",
    "DIRECTUS_DB_PASSWORD",
]

HANDSHAKE_MESSAGE = """
AZIONE MANUALE RICHIESTA
========================
Configurazione MCP scritta in .mcp.json.

Per continuare:
  1. Esci da questa sessione Claude Code
  2. Riavvia: claude --continue
  3. Ri-invoca: /fe-from-migration
""".strip()

NO_MCP_MESSAGE = """
MCP directus-postgres saltato (credenziali DB Directus non fornite).
Introspezione userà solo REST (funzionalità ridotta ma supportata).
""".strip()


def _has_all(env: dict[str, str], keys: list[str]) -> bool:
    return all(env.get(k) for k in keys)


def _build_directus_postgres_entry(env: dict[str, str]) -> dict[str, Any]:
    return {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env": {
            "POSTGRES_HOST": env["DIRECTUS_DB_HOST"],
            "POSTGRES_PORT": env["DIRECTUS_DB_PORT"],
            "POSTGRES_DB": env["DIRECTUS_DB_NAME"],
            "POSTGRES_USER": env["DIRECTUS_DB_USER"],
            "POSTGRES_PASSWORD": env["DIRECTUS_DB_PASSWORD"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--mcp-file", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    args = parser.parse_args(argv)

    env = load_dotenv(args.env_file)
    store = StateStore(args.state_file)

    if not _has_all(env, DIRECTUS_DB_KEYS):
        print(NO_MCP_MESSAGE)
        store.set("phase", "awaiting_restart")
        print(HANDSHAKE_MESSAGE)
        return 0

    if args.mcp_file.exists():
        mcp_cfg: dict[str, Any] = json.loads(args.mcp_file.read_text(encoding="utf-8"))
    else:
        mcp_cfg = {}

    if not isinstance(mcp_cfg.get("mcpServers"), dict):
        mcp_cfg["mcpServers"] = {}
    servers = mcp_cfg["mcpServers"]
    servers["directus-postgres"] = _build_directus_postgres_entry(env)

    args.mcp_file.write_text(json.dumps(mcp_cfg, indent=2), encoding="utf-8")
    # Windows / non-POSIX filesystems may not support chmod
    with contextlib.suppress(OSError):
        args.mcp_file.chmod(0o600)
    store.set("phase", "awaiting_restart")
    print("MCP directus-postgres installato.")
    print(HANDSHAKE_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
