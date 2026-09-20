"""Authoring architecture decisions, and adopting a curated practice pack as one.

An ADR is the only thing in the pyramid that carries machine-readable rules, so
writing one is how a project teaches the guard something new."""
from __future__ import annotations

import re as _re

from torsor_helper import practices as _practices
from torsor_helper.budget import truncate_to_tokens
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

def list_practices(store, config, language=None) -> str:
    """Render the curated best-practice pack(s): one language, or every pack
    detected in the repo when language is None."""
    cpt = config.budgets.chars_per_token
    budget = config.budgets.practices_tokens
    if language is None:
        detected = _practices.detect_languages(store.paths.root)
        if not detected:
            return "No supported languages detected. Available packs: " + ", ".join(
                _practices.available_languages()
            )
        # Every detected pack at once is the largest response the server can
        # return; ask for one language to get it whole.
        return truncate_to_tokens("\n\n".join(_practices.render(lang) for lang in detected), budget, cpt)
    try:
        return truncate_to_tokens(_practices.render(language), budget, cpt)
    except KeyError:
        return f"Unknown pack {language!r}. Available: " + ", ".join(_practices.available_languages())

def adopt_practices(store, config, language) -> dict:
    """Adopt a best-practice pack: records ONE ADR carrying the pack's
    machine-readable rules (guard enforces them) + prose principles."""
    try:
        payload = _practices.adr_payload(language)
    except KeyError:
        return {
            "adopted": False,
            "message": f"Unknown pack {language!r}. Available: "
                       + ", ".join(_practices.available_languages()),
        }
    slug = _slug(payload["title"])
    if store.paths.decisions_dir.exists():
        for existing in store.paths.decisions_dir.glob("*.md"):
            if slug in existing.stem:
                return {"adopted": False, "message": f"Already adopted: {existing} (edit or supersede it instead)."}
    path = record_decision(store, **payload)
    return {
        "adopted": True,
        "path": path,
        "message": (
            f"Adopted the {language} pack → {path}\n"
            "Next: `torsor guard --update-baseline` to grandfather existing code, "
            "then `torsor rules --write AGENTS.md` to refresh the prompt block."
        ),
    }
