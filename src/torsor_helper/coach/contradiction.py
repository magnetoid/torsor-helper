"""Two active decisions that disagree with each other.

A growing ADR set develops this failure quietly: a decision is reversed in a new
ADR and the old one is never marked superseded, so the guard enforces one rule
and the agent reads the other. No linter can see it, because both notes are
individually fine.

Detection is lexical, not semantic, and that is deliberate. The obvious design
is "two decisions with near-duplicate embedding vectors and opposite polarity",
but torsor's default embedder is the hashing fallback — 384 md5 buckets with no
IDF — and Phase 2 measured exactly what it does with a similarity threshold: it
*fabricates* matches, because every text has some similarity to every other. A
check that fires on nothing real is worse than no check, so the similarity test
here is term overlap, which means the same thing on every install with or
without the `embeddings` extra.

Precision over recall (ADR 0010). Both thresholds are set so that torsor's own
ADRs produce nothing, and there is a test asserting that: a check that fires on
a set of decisions known not to contradict is wrong, not sensitive.
"""
from __future__ import annotations

import re

from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_WORD = re.compile(r"[a-z][a-z0-9_]+")

# Words that carry no topic. Kept short on purpose: a long list starts deciding
# what a decision is about, and the overlap threshold already does that.
_STOP = frozenset("""
the a an and or of for to in on at by with from as is are be we our this that
it its into over under than then so but not no all any each per via use using
""".split())

_NEGATIVE = (
    "never", "avoid", "avoids", "don't", "dont", "do not", "does not", "no longer",
    "stop", "deprecate", "deprecated", "forbid", "forbidden", "must not", "drop",
    "without", "instead of", "rather than",
)
_POSITIVE = ("always", "must", "use", "uses", "prefer", "adopt", "standardize", "require", "keep")

# Both are tuned against this repo's ADRs, which do not contradict each other.
_MIN_OVERLAP = 0.55   # Jaccard over the topic words of two decision titles
_MIN_TOPIC_WORDS = 3  # a two-word title overlaps with too much by accident


def polarity(text: str) -> int:
    """+1 asserts, -1 forbids, 0 says neither.

    Negatives win over positives, because "never use X" contains "use": the
    prohibition is the claim, and the verb it governs is not.
    """
    low = text.lower()
    if any(marker in low for marker in _NEGATIVE):
        return -1
    return 1 if any(re.search(rf"\b{m}\b", low) for m in _POSITIVE) else 0


def _topic_words(title: str) -> set[str]:
    return {w for w in _WORD.findall(title.lower()) if w not in _STOP} - set(
        w for w in _NEGATIVE + _POSITIVE if " " not in w
    )


def _overlap(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _pair_key(a: str, b: str) -> str:
    """Order-independent, so dismissing a pair sticks whichever way round the
    two notes are compared next time."""
    first, second = sorted((a, b))
    return f"contradiction:{first}:{second}"


def _active_decisions(store: Store):
    if not store.paths.decisions_dir.is_dir():
        return []
    out = []
    for path in sorted(store.paths.decisions_dir.glob("*.md")):
        try:
            note = store.read_note(path)
        except (OSError, UnicodeDecodeError):
            continue
        fm = note.frontmatter
        if fm.type != "decision" or fm.status == "superseded":
            continue
        supersedes = getattr(fm, "supersedes", None)
        out.append((path, note, [str(s) for s in supersedes] if isinstance(supersedes, list) else []))
    return out


def find_contradictions(store: Store) -> list[Recommendation]:
    """Pairs of active decisions that are about the same thing and disagree."""
    decisions = _active_decisions(store)
    out: list[Recommendation] = []
    for i, (path_a, note_a, sup_a) in enumerate(decisions):
        words_a = _topic_words(note_a.title)
        if len(words_a) < _MIN_TOPIC_WORDS:
            continue
        pol_a = polarity(note_a.title)
        if pol_a == 0:
            continue
        for path_b, note_b, sup_b in decisions[i + 1:]:
            pol_b = polarity(note_b.title)
            if pol_b == 0 or pol_a == pol_b:
                continue
            # An explicit supersedes link is how a decision is *meant* to be
            # reversed; flagging it would punish the correct workflow.
            if any(s in path_b.stem for s in sup_a) or any(s in path_a.stem for s in sup_b):
                continue
            words_b = _topic_words(note_b.title)
            if len(words_b) < _MIN_TOPIC_WORDS or _overlap(words_a, words_b) < _MIN_OVERLAP:
                continue
            out.append(Recommendation(
                kind="contradiction", severity="suggest",
                message=(
                    f"{path_a.name} ({note_a.title!r}) and {path_b.name} ({note_b.title!r}) "
                    "are about the same thing and state opposite decisions — if one replaced "
                    "the other, mark the old one `status: superseded`."
                ),
                action=f"reconcile {path_a.name} and {path_b.name}",
                source=str(path_a),
                key=_pair_key(path_a.name, path_b.name),
                score=_overlap(words_a, words_b),
            ))
    return out
