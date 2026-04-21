"""State machine persistence for wp-to-directus skill."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


INITIAL_STATE: Dict[str, Any] = {
    "phase": "init",
    "mode": None,
    "started_at": None,
    "updated_at": None,
    "checkpoints": {
        "env_validated": False,
        "mcp_installed": False,
        "docker_up": False,
        "discovery_done": False,
        "schema_done": False,
        "migrate_done": False,
        "verify_done": False,
        "report_done": False,
    },
    "migrate_subphase": {
        "authors_done": False,
        "categories_done": False,
        "tags_done": False,
        "media_done_count": 0,
        "posts_done_count": 0,
        "pages_done_count": 0,
        "custom_types_done": [],
        "relationships_done": False,
    },
    "discovery": {
        "plugins": [],
        "custom_post_types": [],
        "custom_taxonomies": [],
        "custom_meta_keys": [],
        "non_core_tables": [],
    },
    "counts": {"wp": {}, "directus": {}},
    "errors": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            state = json.loads(json.dumps(INITIAL_STATE))
            state["started_at"] = _now()
            state["updated_at"] = state["started_at"]
            self._write(state)
            return state
        with self.path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        return _deep_merge(INITIAL_STATE, loaded)

    def save(self, state: Dict[str, Any]) -> None:
        state["updated_at"] = _now()
        self._write(state)

    def set_phase(self, phase: str) -> None:
        state = self.load()
        state["phase"] = phase
        self.save(state)

    def mark_checkpoint(self, name: str) -> None:
        state = self.load()
        state["checkpoints"][name] = True
        self.save(state)

    def append_error(self, **kw) -> None:
        state = self.load()
        entry = {"timestamp": _now(), **kw}
        state.setdefault("errors", []).append(entry)
        self.save(state)

    def _write(self, state: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
