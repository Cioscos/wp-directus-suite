"""Atomic JSON state persistence."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.data = {}
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._backup_corrupt()
            self.data = {}

    def _backup_corrupt(self) -> None:
        backup = self.path.with_suffix(f".json.corrupt.{int(time.time())}")
        self.path.rename(backup)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._save()

    def update(self, patch: dict[str, Any]) -> None:
        self.data.update(patch)
        self._save()

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def mark_done(self, bucket: str, item: str) -> None:
        checkpoints = self.data.setdefault("checkpoints", {})
        done = checkpoints.setdefault(bucket, [])
        if item not in done:
            done.append(item)
            self._save()

    def is_done(self, bucket: str, item: str) -> bool:
        return item in self.data.get("checkpoints", {}).get(bucket, [])

    def done_items(self, bucket: str) -> list[str]:
        return list(self.data.get("checkpoints", {}).get(bucket, []))
