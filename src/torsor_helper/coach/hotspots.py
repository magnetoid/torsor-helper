from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from torsor_helper import gitinfo, languages
from torsor_helper.cartographer import iter_source_files
from torsor_helper.models import Recommendation


def _is_git_repo(root: Path) -> bool:
    return gitinfo.is_repo(root)


def history_args(history_days: int) -> list[str]:
    """`git log` bounds shared by churn and temporal coupling. Both used to read
    the entire history, so `torsor coach` got slower every year regardless of
    how much code there was."""
    return ["--since", f"{history_days} days ago"] if history_days and history_days > 0 else []


def _churn(root: Path, history_days: int = 365) -> Counter:
    out = gitinfo.output(root, "log", *history_args(history_days), "--name-only", "--pretty=format:")
    # Hoisted: it was evaluated once per line of `git log` output, and every
    # call re-checks that each language's modules import.
    exts = languages.source_extensions()
    return Counter(line.strip() for line in out.splitlines() if line.strip().endswith(exts))


def _complexity(path: Path) -> int:
    return languages.complexity(path)


# Every branch node the complexity proxies count needs at least one of these
# tokens in the source: python.py counts If/For/While/Try/BoolOp (if, elif, for,
# while, try, and, or); javascript.py counts if/for/while/do/case/catch,
# ternaries (?) and && || ??; go.py counts if/for/case/select and && ||.
# Counting them with a regex — in strings and comments too — can only
# over-count, so newlines + tokens is an upper bound on the real complexity.
# tests/test_hotspot_pruning.py checks that on every source file in this repo.
_BRANCH_TOKENS = re.compile(r"\b(?:if|elif|for|while|try|and|or|do|case|catch|select)\b|&&|\|\||\?")
_BOUNDED_LANGUAGES = {"python", "javascript", "typescript", "go"}


def complexity_bound(path: Path, text: str) -> float:
    """An upper bound on `languages.complexity(path)`, without parsing. Infinite
    for a language whose branch tokens it does not know — never pruned."""
    spec = languages.spec_for(path)
    if spec is None or spec.name not in _BOUNDED_LANGUAGES:
        return float("inf")
    return text.count("\n") + 1 + len(_BRANCH_TOKENS.findall(text))


def _score_all(present) -> list[tuple[str, int, int, int]]:
    scored = []
    for rel, count, path in present:
        comp = _complexity(path)
        if comp > 0:
            scored.append((rel, count * comp, count, comp))
    return scored


def _top_scored(present, limit: int) -> list[tuple[str, int, int, int]]:
    """The same top `limit` as _score_all, parsing only files that can still
    make it.

    It computed complexity for every file git had ever touched in the window —
    3 200 parses, ~20 s on a real project — to report three. Candidates are
    visited by churn x upper-bound, descending; once even the bound of the next
    one falls strictly below the k-th real score found, nothing after it can
    enter the top k (every later bound is smaller still). Strictly below, so a
    candidate that could TIE is still scored and the (score, path) tie-break
    comes out exactly as the unpruned version's."""
    bounded = []
    for rel, count, path in present:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        bounded.append((count * complexity_bound(path, text), rel, count, path))
    bounded.sort(key=lambda t: (-t[0], t[1]))

    scored: list[tuple[str, int, int, int]] = []
    for upper, rel, count, path in bounded:
        if len(scored) >= limit:
            kth = sorted((s[1] for s in scored), reverse=True)[limit - 1]
            if upper < kth:
                break
        comp = _complexity(path)
        if comp > 0:
            scored.append((rel, count * comp, count, comp))
    return scored


def find_hotspots(root: Path, limit: int = 3, history_days: int = 365, *,
                  prune: bool = True) -> list[Recommendation]:
    """Rank current source files by churn × complexity and surface the top few as
    'hotspot' recommendations — where to refactor / add tests first. Degrades to
    [] outside a git repo (so offline/non-git runs are quiet)."""
    root = Path(root)
    if not _is_git_repo(root):
        return []
    churn = _churn(root, history_days)
    if not churn:
        return []
    source = {p.relative_to(root).as_posix(): p for p in iter_source_files(root)}
    present = [(rel, count, source[rel]) for rel, count in churn.items() if rel in source]
    scored = _top_scored(present, limit) if prune else _score_all(present)
    scored.sort(key=lambda t: (-t[1], t[0]))

    out: list[Recommendation] = []
    for rel, score, count, comp in scored[:limit]:
        out.append(Recommendation(
            kind="hotspot", severity="suggest",
            message=(
                f"{rel} is a hotspot — changed {count}× with complexity {comp} "
                f"(churn×complexity={score}). Refactor or add tests here first."
            ),
            action=f"review {rel}", source=rel, key=f"hotspot:{rel}", score=float(score),
        ))
    return out
