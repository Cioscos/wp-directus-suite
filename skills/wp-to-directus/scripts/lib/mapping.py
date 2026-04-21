"""Persistent wp_original_id -> directus id mapping per collection."""

import json
from pathlib import Path
from typing import Dict


class MappingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: Dict[str, Dict[str, int]] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, collection: str, wp_id: int):
        return self.data.get(collection, {}).get(str(wp_id))

    def put(self, collection: str, wp_id: int, directus_id) -> None:
        self.data.setdefault(collection, {})[str(wp_id)] = directus_id
        self._flush()

    def collection(self, name: str) -> Dict[str, int]:
        return self.data.get(name, {})

    def _flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
