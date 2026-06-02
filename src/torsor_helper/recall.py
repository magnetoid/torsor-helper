from __future__ import annotations

import re

from torsor_helper.budget import estimate_tokens
from torsor_helper.models import Note, RecallHit, RecallResult, Tier
from torsor_helper.snippets import best_snippet

_WORD = re.compile(r"\w+")

_DEFAULT_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5,
    Tier.ARCHITECTURE: 1.4,
    Tier.ACTIVE: 1.2,
    Tier.MAP: 1.1,
    Tier.EPISODIC: 1.0,
}


def keyword_recall(
    notes: list[Note],
    query: str,
    limit: int = 8,
    chars_per_token: int = 4,
    max_tokens: int = 1500,
    tier_weights: dict[Tier, float] | None = None,
) -> RecallResult:
    weights = tier_weights or _DEFAULT_TIER_WEIGHTS
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    scored: list[RecallHit] = []
    for note in notes:
        haystack = f"{note.title}\n{note.body}".lower()
        raw = sum(haystack.count(term) for term in terms)
        if raw == 0:
            continue
        score = raw * weights.get(note.tier, 1.0)
        scored.append(
            RecallHit(
                path=str(note.path),
                title=note.title,
                tier=note.tier,
                score=score,
                snippet=best_snippet(note.body, terms),
            )
        )

    scored.sort(key=lambda h: (-h.score, h.path))

    selected: list[RecallHit] = []
    used = 0
    for hit in scored[:limit]:
        cost = estimate_tokens(hit.snippet, chars_per_token)
        if selected and used + cost > max_tokens:
            break
        selected.append(hit)
        used += cost
    return RecallResult(query=query, hits=selected, total_tokens=used)
