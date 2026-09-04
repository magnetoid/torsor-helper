from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

from torsor_helper import languages
from torsor_helper.cartographer import iter_source_files
from torsor_helper.models import Recommendation


def _is_git_repo(root: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def _churn(root: Path) -> Counter:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return Counter()
    return Counter(
        line.strip() for line in out.splitlines() if line.strip().endswith(languages.source_extensions())
    )


def _complexity(path: Path) -> int:
    return languages.complexity(path)


def find_hotspots(root: Path, limit: int = 3) -> list[Recommendation]:
    """Rank current source files by churn × complexity and surface the top few as
    'hotspot' recommendations — where to refactor / add tests first. Degrades to
    [] outside a git repo (so offline/non-git runs are quiet)."""
    root = Path(root)
    if not _is_git_repo(root):
        return []
    churn = _churn(root)
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
