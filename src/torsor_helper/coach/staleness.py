from __future__ import annotations

import re

from torsor_helper.models import Recommendation
from torsor_helper.store import Store

# Staleness = memory that contradicts current code. The #1 open problem in agent
# memory (2026) is stale notes making agents "confidently wrong". These detectors
# are deliberately DETERMINISTIC and HIGH-PRECISION: they fire only on unambiguous
# signals (a wikilink or file path that resolves to nothing), because a false
# positive here just trains the user to ignore the Coach. Fuzzier signals
# (age/churn decay, symbol-mention heuristics) are intentionally omitted — see
# ADR 0010. Both detectors are index-free.

# A repo-relative source path: at least one `dir/` segment then `file.ext`. The
# leading-slash negative lookbehind keeps it from matching inside a URL; the
# trailing word-char negative lookahead stops `.js` matching inside `.json`.
_PATH_RE = re.compile(
    r"(?<![\w/])((?:[\w.-]+/)+[\w.-]+\.(?:py|pyi|js|jsx|mjs|ts|tsx|go|rs))(?![A-Za-z0-9_])"
)
_URL_RE = re.compile(r"https?://\S+")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")


def _rel(store: Store, path) -> str:
    try:
        return path.relative_to(store.paths.root).as_posix()
    except ValueError:
        return str(path)


def check_dangling_links(store: Store) -> list[Recommendation]:
    """Notes whose [[wikilink]] points to a note that no longer exists — the
    highest-precision staleness signal (deletion is unambiguous)."""
    note_slugs = {p.stem for p in store.iter_note_paths()}
    out: list[Recommendation] = []
    for note in store.iter_notes():
        rel = _rel(store, note.path)
        for slug in store.extract_wikilinks(note.body):
            if slug not in note_slugs:
                out.append(Recommendation(
                    kind="dangling_link", severity="suggest",
                    message=f"{rel} links to [[{slug}]], which no longer exists.",
                    action=f"fix or remove the [[{slug}]] link in {rel}",
                    source=rel, key=f"dangling_link:{rel}:{slug}",
                ))
    return out


def check_path_refs(store: Store) -> list[Recommendation]:
    """Notes citing a repo-relative source path that no longer exists on disk.
    High-precision by construction: only paths written in an inline `code` span
    are checked — illustrative example paths in prose are conventionally in
    "double quotes", and real references in `backticks`. Paths need a `/` (bare
    filenames are too ambiguous); fenced blocks and URLs are stripped first."""
    out: list[Recommendation] = []
    for note in store.iter_notes():
        rel = _rel(store, note.path)
        body = _FENCE_RE.sub("", note.body)
        seen: set[str] = set()
        for span in _INLINE_CODE.findall(body):
            span = _URL_RE.sub("", span)
            for m in _PATH_RE.finditer(span):
                token = m.group(1)
                if token in seen:
                    continue
                seen.add(token)
                if not (store.paths.root / token).exists():
                    out.append(Recommendation(
                        kind="stale_path", severity="suggest",
                        message=f"{rel} references `{token}`, which no longer exists.",
                        action=f"update or remove the `{token}` reference in {rel}",
                        source=rel, key=f"stale_path:{rel}:{token}",
                    ))
    return out


def run_staleness(store: Store) -> list[Recommendation]:
    return [*check_dangling_links(store), *check_path_refs(store)]
