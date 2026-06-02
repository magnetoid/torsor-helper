from __future__ import annotations

import re
from pathlib import Path

from torsor_helper.models import Frontmatter
from torsor_helper.store import Store

# Journal entries are written by store.append_journal as:  "## HH:MM · <kind>\n\n<content>\n"
_ENTRY = re.compile(r"^## \d{2}:\d{2} · (\S+)\n(.*?)(?=^## \d{2}:\d{2} ·|\Z)", re.MULTILINE | re.DOTALL)
_MINED_KINDS = ("learning", "decision", "rejection", "blocker")


def parse_journal_entries(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for match in _ENTRY.finditer(body):
        kind = match.group(1)
        lines = [ln for ln in match.group(2).splitlines() if not ln.startswith("Links:")]
        content = "\n".join(lines).strip()
        if content:
            out.append((kind, content))
    return out


def _all_entries(store: Store) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if store.paths.journal_dir.exists():
        for jpath in sorted(store.paths.journal_dir.glob("*.md")):
            out.extend(parse_journal_entries(store.read_note(jpath).body))
    return out


def mine_insights(store: Store) -> list[Path]:
    by_kind: dict[str, list[str]] = {}
    for kind, content in _all_entries(store):
        if kind in _MINED_KINDS:
            by_kind.setdefault(kind, []).append(content)

    store.paths.insights_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for kind, items in by_kind.items():
        seen: set[str] = set()
        uniq = [it for it in items if not (it in seen or seen.add(it))]
        body = "\n".join(f"- {it}" for it in uniq)
        target = store.paths.insights_dir / f"{kind}.md"
        store.write_note(target, Frontmatter(type="insight", tags=["insight"], kind=kind), f"Mined {kind}s", body)
        written.append(target)
    return written


def find_duplicate_entries(store: Store) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for _kind, content in _all_entries(store):
        counts[content] = counts.get(content, 0) + 1
    dups = [(content, n) for content, n in counts.items() if n > 1]
    dups.sort(key=lambda t: (-t[1], t[0]))
    return dups
