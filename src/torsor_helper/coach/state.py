from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable


class CoachState:
    """Per-recommendation tracking, persisted as JSON.

    Four facts per key: whether it was dismissed, how many times it has been
    shown (which drives the decay that keeps the Coach from nagging), when it
    was first seen, and when it was last shown.

    Non-derivable — this is the user's own history with the Coach, which is why
    it lives under `.torsor/state/` and not in the disposable index. A corrupt
    or missing file still resets cleanly: losing it costs a repeated
    recommendation, never data.
    """

    def __init__(self, path: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self.path = Path(path)
        self.clock = clock
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def _entry(self, key: str) -> dict:
        return self.data.setdefault(key, {})

    def _today(self) -> str:
        return self.clock().date().isoformat()

    def is_dismissed(self, key: str) -> bool:
        return bool(self.data.get(key, {}).get("dismissed", False))

    def dismiss(self, key: str) -> None:
        self._entry(key)["dismissed"] = True

    def seen(self, key: str) -> None:
        entry = self._entry(key)
        entry["times_shown"] = int(entry.get("times_shown", 0)) + 1
        entry.setdefault("first_seen", self._today())
        entry["last_shown"] = self._today()

    def times_shown(self, key: str) -> int:
        return int(self.data.get(key, {}).get("times_shown", 0))

    def first_seen(self, key: str) -> str:
        return str(self.data.get(key, {}).get("first_seen", "") or "")

    def last_shown(self, key: str) -> str:
        return str(self.data.get(key, {}).get("last_shown", "") or "")

    def days_open(self, key: str) -> int:
        """How long this recommendation has been unaddressed, in days. 0 when it
        has never been shown or the stamp is unreadable — an unknown age reads
        as "new", which is the quiet direction to be wrong in."""
        stamp = self.first_seen(key)
        if not stamp:
            return 0
        try:
            return max(0, (self.clock().date() - date.fromisoformat(stamp)).days)
        except ValueError:
            return 0

    def resolve_missing(self, present: Iterable[str]) -> list[str]:
        """Keys that were shown before and are not being produced any more — i.e.
        the problem was fixed — removed from state and returned, so they are
        reported exactly once.

        A key that was never shown is not resolved: it was never surfaced, so it
        was never fixed, and saying otherwise would be a lie about work the user
        did not do. A dismissed key is not resolved either, and keeps its
        dismissal — otherwise forgetting it here would make it come back.
        """
        current = set(present)
        gone = sorted(
            key for key, entry in self.data.items()
            if key not in current
            and int(entry.get("times_shown", 0)) > 0
            and not entry.get("dismissed", False)
        )
        for key in gone:
            del self.data[key]
        return gone

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
