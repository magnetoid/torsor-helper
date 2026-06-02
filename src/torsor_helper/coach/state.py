from __future__ import annotations

import json
from pathlib import Path


class CoachState:
    """Per-recommendation tracking (dismissed / times_shown), persisted as JSON.

    Derived and disposable — a corrupt or missing file resets cleanly.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def _entry(self, key: str) -> dict:
        return self.data.setdefault(key, {})

    def is_dismissed(self, key: str) -> bool:
        return bool(self.data.get(key, {}).get("dismissed", False))

    def dismiss(self, key: str) -> None:
        self._entry(key)["dismissed"] = True

    def seen(self, key: str) -> None:
        entry = self._entry(key)
        entry["times_shown"] = int(entry.get("times_shown", 0)) + 1

    def times_shown(self, key: str) -> int:
        return int(self.data.get(key, {}).get("times_shown", 0))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
