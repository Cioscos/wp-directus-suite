"""Generate / merge `.mcp.json` for the wp-to-directus skill.

Always writes `wordpress-mysql`. Writes `directus-postgres` only when every
DIRECTUS_DB_* var is set in `.env`. Merges with any existing `.mcp.json`
without clobbering unrelated entries.

After success, prints the restart handshake message and sets state phase to
`awaiting_restart`.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore

MANAGED_KEYS = {"wordpress-mysql", "directus-postgres"}


def url_encode_password(pwd: str) -> str:
    return quote(pwd, safe="")


def build_mcp_config(env: dict) -> dict:
    cfg = {"mcpServers": {}}

    mysql_pwd = url_encode_password(env.get("WP_DB_PASSWORD", ""))
    mysql_dsn = (
        f"mysql://{env.get('WP_DB_USER','')}:{mysql_pwd}"
        f"@{env.get('WP_DB_HOST','')}:{env.get('WP_DB_PORT','3306')}"
        f"/{env.get('WP_DB_NAME','')}"
    )
    cfg["mcpServers"]["wordpress-mysql"] = {
        "command": "npx",
        "args": ["-y", "@bytebase/dbhub@latest", "--transport", "stdio",
                 "--dsn", mysql_dsn],
    }

    pg_required = ("DIRECTUS_DB_HOST", "DIRECTUS_DB_PORT",
                   "DIRECTUS_DB_USER", "DIRECTUS_DB_PASSWORD",
                   "DIRECTUS_DB_NAME")
    if all(env.get(k) for k in pg_required):
        pg_pwd = url_encode_password(env["DIRECTUS_DB_PASSWORD"])
        pg_dsn = (
            f"postgresql://{env['DIRECTUS_DB_USER']}:{pg_pwd}"
            f"@{env['DIRECTUS_DB_HOST']}:{env['DIRECTUS_DB_PORT']}"
            f"/{env['DIRECTUS_DB_NAME']}"
        )
        cfg["mcpServers"]["directus-postgres"] = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres", pg_dsn],
        }

    return cfg


def merge_mcp(existing: dict, new: dict) -> dict:
    merged = json.loads(json.dumps(existing or {"mcpServers": {}}))
    merged.setdefault("mcpServers", {})
    for k, v in new.get("mcpServers", {}).items():
        merged["mcpServers"][k] = v
    return merged


def load_env(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def print_restart_handshake(has_postgres: bool) -> None:
    servers = ["  - wordpress-mysql (WP read)"]
    if has_postgres:
        servers.append("  - directus-postgres (Directus verify, read-only)")
    msg = f"""
========================================
  AZIONE MANUALE RICHIESTA
========================================

MCP server configurati in .mcp.json:
{chr(10).join(servers)}

Claude deve essere riavviato per caricare MCP:

  1. Esci da questa sessione Claude Code
  2. Riavvia: `claude --continue` (oppure `--resume <session>`)
  3. Ri-invoca: /wp-to-directus

Stato salvato in state/.state.json (project root).
Skill riprende automaticamente dalla fase successiva.
========================================
"""
    print(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--mcp-file", required=True)
    ap.add_argument("--state-file", required=True)
    args = ap.parse_args()

    env = load_env(Path(args.env_file))
    mcp_path = Path(args.mcp_file)
    existing = json.loads(mcp_path.read_text(encoding="utf-8")) \
        if mcp_path.exists() else {"mcpServers": {}}

    new_cfg = build_mcp_config(env)
    merged = merge_mcp(existing, new_cfg)

    mcp_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")

    state = StateStore(Path(args.state_file))
    state.mark_checkpoint("mcp_installed")
    state.set_phase("awaiting_restart")

    print_restart_handshake(
        has_postgres="directus-postgres" in new_cfg["mcpServers"])


if __name__ == "__main__":
    main()
