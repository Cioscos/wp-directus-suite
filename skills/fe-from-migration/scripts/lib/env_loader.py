"""Parse .env files into dict (no shell exec)."""

from __future__ import annotations

from pathlib import Path


def load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict.

    Skips blank lines and comments. Strips surrounding single/double quotes.
    Returns empty dict if file missing.
    """
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env
