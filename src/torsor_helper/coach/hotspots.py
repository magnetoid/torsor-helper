from __future__ import annotations

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
    return Counter(
        line.strip() for line in out.splitlines() if line.strip().endswith(languages.source_extensions())
    )


def _complexity(path: Path) -> int:
    return languages.complexity(path)


def find_hotspots(root: Path, limit: int = 3, history_days: int = 365) -> list[Recommendation]:
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

    scored: list[tuple[str, int, int, int]] = []
    for rel, count in churn.items():
        path = source.get(rel)  # only files still present and not ignored
        if path is None:
            continue
        comp = _complexity(path)
        if comp <= 0:
            continue
        scored.append((rel, count * comp, count, comp))
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
