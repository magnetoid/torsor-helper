from __future__ import annotations

import re

_BLANK = re.compile(r"\n\s*\n")


def _split_sections(body: str) -> list[str]:
    """Split a note body into candidate snippet windows on blank lines.

    A Markdown heading (`## ...`) followed directly by its text stays in one
    block, so a heading-term match can bias toward that section.
    """
    return [s for s in (chunk.strip() for chunk in _BLANK.split(body)) if s]


def _window(text: str, terms: list[str], width: int) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if t in low), default=-1)
    if pos < 0:
        return text[:width].strip()
    start = max(0, pos - width // 4)
    return text[start : start + width].strip()


def best_snippet(body: str, terms: list[str], width: int = 240) -> str:
    """Return the most query-relevant window of ``body``.

    Scores each blank-line-delimited section by summed term frequency (with a
    small bonus when a query term appears in a leading Markdown heading) and
    returns a width-bounded window of the best section, centred on its first
    term hit. Falls back to a leading prefix when nothing matches. Pure,
    deterministic, no dependencies — replaces the old first-hit-only window so
    recall surfaces the densest evidence instead of the earliest mention.
    """
    terms = [t for t in terms if t]
    if not terms:
        return body[:width].strip()

    best: str | None = None
    best_score = 0
    for section in _split_sections(body):
        low = section.lower()
        score = sum(low.count(t) for t in terms)
        head = section.split("\n", 1)[0].lower()
        if head.startswith("#") and any(t in head for t in terms):
            score += 1
        if score > best_score:  # strict: first section wins ties (earliest)
            best_score = score
            best = section

    if best is None:  # no term occurs anywhere
        return body[:width].strip()
    return _window(best, terms, width)
