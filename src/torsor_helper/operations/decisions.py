"""Authoring architecture decisions, and adopting a curated practice pack as one.

An ADR is the only thing in the pyramid that carries machine-readable rules, so
writing one is how a project teaches the guard something new."""
from __future__ import annotations

import re as _re

from torsor_helper.models import Frontmatter


def _next_adr_number(store) -> int:
    nums = []
    if store.paths.decisions_dir.exists():
        for p in store.paths.decisions_dir.glob("*.md"):
            m = _re.match(r"(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1

def _slug(title: str) -> str:
    s = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "decision"

def _find_adr(store, ref):
    """Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2')."""
    if not store.paths.decisions_dir.exists():
        return None
    ref = str(ref)
    for p in sorted(store.paths.decisions_dir.glob("*.md")):
        if p.stem == ref or p.name == ref or p.stem.startswith(ref + "-"):
            return p
        m = _re.match(r"(\d+)", p.name)
        if m and m.group(1).lstrip("0") == ref.lstrip("0"):
            return p
    return None

def record_decision(store, title, context, decision, consequences="", rules=None, supersedes=None) -> str:
    number = _next_adr_number(store)
    new_stem = f"{number:04d}-{_slug(title)}"

    fm_data = {"type": "decision", "status": "accepted", "tags": ["adr"], "rules": rules or []}
    if supersedes:
        old = _find_adr(store, supersedes)
        if old is not None:
            old_note = store.read_note(old)
            old_data = old_note.frontmatter.model_dump(exclude_none=True)
            old_data["status"] = "superseded"
            old_data["superseded_by"] = new_stem
            store.write_note(old, Frontmatter.model_validate(old_data), old_note.title, old_note.body)
            fm_data["supersedes"] = old.stem

    body = (
        f"## Context\n{context}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    target = store.paths.decisions_dir / f"{new_stem}.md"
    store.write_note(target, Frontmatter.model_validate(fm_data), f"ADR {number:04d}: {title}", body)
    return str(target)
