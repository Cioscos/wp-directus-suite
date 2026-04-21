"""Validate .env, prompt missing vars, ping connections.

Invoked by skill during `env_check` phase. Writes checkpoint on success.

Usage:
  python scripts/env_check.py --mode test
  python scripts/env_check.py --mode external
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent.parent.parent   # project root from .claude/skills/wp-to-directus/scripts
if not (PROJECT_DIR / "docker-compose.yml").exists():
    PROJECT_DIR = Path.cwd()

sys.path.insert(0, str(SCRIPT_DIR))
from lib.state import StateStore
from lib.wp_mysql import MySQLClient
from lib.directus_api import DirectusClient


COMMON_VARS = [
    "WP_DB_HOST", "WP_DB_PORT", "WP_DB_USER", "WP_DB_PASSWORD", "WP_DB_NAME",
    "WP_SITE_URL",
    "DIRECTUS_URL", "DIRECTUS_ADMIN_TOKEN",
]

TEST_ONLY_VARS = [
    "WP_INTERNAL_URL",
    "MYSQL_ROOT_PASSWORD",
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
    "DIRECTUS_SECRET", "DIRECTUS_ADMIN_EMAIL", "DIRECTUS_ADMIN_PASSWORD",
    "DIRECTUS_DB_HOST", "DIRECTUS_DB_PORT",
    "DIRECTUS_DB_USER", "DIRECTUS_DB_PASSWORD", "DIRECTUS_DB_NAME",
]

EXTERNAL_OPTIONAL_VARS = [
    "DIRECTUS_DB_HOST", "DIRECTUS_DB_PORT",
    "DIRECTUS_DB_USER", "DIRECTUS_DB_PASSWORD", "DIRECTUS_DB_NAME",
]

SECRET_KEYS = {"PASSWORD", "TOKEN", "SECRET"}


def required_vars_for_mode(mode: str) -> list:
    if mode == "test":
        return list(COMMON_VARS) + list(TEST_ONLY_VARS)
    return list(COMMON_VARS)


def is_secret(key: str) -> bool:
    return any(s in key.upper() for s in SECRET_KEYS)


def load_env(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def write_env(path: Path, env: dict) -> None:
    lines = [f"{k}={v}" for k, v in env.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def prompt_missing(env: dict, required: list) -> dict:
    for k in required:
        if env.get(k):
            continue
        if is_secret(k):
            env[k] = getpass.getpass(f"{k} (hidden): ")
        else:
            env[k] = input(f"{k}: ").strip()
    return env


def ping_all(env: dict, mode: str) -> list:
    # In test mode the Docker stack is started later (phase `docker_or_connect`),
    # so services are not reachable yet — skip ping and only validate env vars.
    if mode == "test":
        return []
    errors = []
    mc = MySQLClient(
        host=env.get("WP_DB_HOST", "localhost"),
        port=int(env.get("WP_DB_PORT", "3306") or "3306"),
        user=env.get("WP_DB_USER", ""),
        password=env.get("WP_DB_PASSWORD", ""),
        database=env.get("WP_DB_NAME", ""),
        docker_service=None,
    )
    if not mc.ping():
        errors.append("WP MySQL ping failed")
    dc = DirectusClient(env.get("DIRECTUS_URL", ""), env.get("DIRECTUS_ADMIN_TOKEN", ""))
    if not dc.ping():
        errors.append("Directus REST ping failed")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["test", "external"], required=True)
    ap.add_argument("--env-file", default=str(PROJECT_DIR / ".env"))
    ap.add_argument("--state-file", default=str(
        SCRIPT_DIR.parent / "state" / ".state.json"))
    args = ap.parse_args()

    env = load_env(Path(args.env_file))
    required = required_vars_for_mode(args.mode)
    env = prompt_missing(env, required)
    write_env(Path(args.env_file), env)
    os.environ.update({k: v for k, v in env.items() if v})

    errors = ping_all(env, args.mode)
    state = StateStore(Path(args.state_file))
    st = state.load()
    st["mode"] = args.mode

    if errors:
        for e in errors:
            print(f"  X {e}")
            state.append_error(phase="env_check", error=e)
        st["phase"] = "env_check"
        state.save(st)
        sys.exit(1)

    st["checkpoints"]["env_validated"] = True
    st["phase"] = "mcp_install"
    state.save(st)
    print(f"  + env validated ({len([k for k in required if env.get(k)])} vars), mode={args.mode}")


if __name__ == "__main__":
    main()
