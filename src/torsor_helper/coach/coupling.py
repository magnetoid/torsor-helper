from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

from torsor_helper import db, gitinfo, languages
from torsor_helper.cartographer import norm_path
from torsor_helper.coach.hotspots import _is_git_repo, history_args
from torsor_helper.models import Recommendation


def _commits(root: Path, history_days: int = 365) -> list[set[str]]:
    """Each commit as the set of source files it touched (via git log --name-only).
    Bounded by the same window as churn — see hotspots.history_args."""
    out = gitinfo.output(
        root, "log", *history_args(history_days), "--no-merges", "--name-only",
        "--pretty=format:#commit#%H",
    )
    commits: list[set[str]] = []
    cur: set[str] | None = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#commit#"):  # unambiguous boundary (a filename can't start with this)
            cur = set()
            commits.append(cur)
        elif cur is not None and line.endswith(languages.source_extensions()):
            cur.add(line)
    return commits


def find_coupling(root: Path, min_commits: int = 3, max_files: int = 40, threshold: float = 0.6, history_days: int = 365):
    """Pairs of files that change together far more often than chance.

    degree = co_changes / min(changes(a), changes(b)). Skips giant commits
    (> max_files .py files — merges/sweeps) and pairs below min_commits.
    Returns [(file_a, file_b, co_changes, degree)] sorted strongest-first.
    Empty outside a git repo (deterministic given history)."""
    root = Path(root)
    if not _is_git_repo(root):
        return []
    changes: Counter[str] = Counter()
    co: Counter[tuple[str, str]] = Counter()
    for files in _commits(root, history_days):
        fs = sorted(files)
        if not fs or len(fs) > max_files:
            continue
        for f in fs:
            changes[f] += 1
        for a, b in combinations(fs, 2):
            co[(a, b)] += 1

    out = []
    for (a, b), c in co.items():
        if c < min_commits or changes[a] < min_commits or changes[b] < min_commits:
            continue
        degree = c / min(changes[a], changes[b])
        if degree >= threshold:
            out.append((a, b, c, degree))
    out.sort(key=lambda t: (-t[3] * t[2], t[0], t[1]))
    return out


def find_coupling_recs(root: Path, conn, limit: int = 3, history_days: int = 365) -> list[Recommendation]:
    """Coupling recs for the top co-changed pairs NOT already linked by an import
    edge (an import explains the coupling; a hidden one doesn't)."""
    pairs = find_coupling(root, history_days=history_days)
    if not pairs:
        return []
    edges: set[tuple[str, str]] = set()
    if conn is not None:
        for m, r in db.module_edges(conn):
            # `m` is a file relpath (needs norm_path); `r` is already the
            # canonical resolved_module key — never re-normalize it.
            nm, nr = norm_path(m), r
            if nm != nr:  # ignore self-edges (a module referencing its own symbols)
                edges.add((nm, nr))

    out: list[Recommendation] = []
    for a, b, co, degree in pairs:
        na, nb = norm_path(a), norm_path(b)
        if na == nb:  # distinct files that collapse to one module — can't import-explain reliably
            continue
        if (na, nb) in edges or (nb, na) in edges:
            continue  # coupling already explained by an import
        out.append(Recommendation(
            kind="coupling", severity="suggest",
            message=(
                f"{a} and {b} change together in {co} commits ({int(degree * 100)}% coupling) but "
                f"neither imports the other — document the hidden dependency or refactor the seam."
            ),
            action=f"link {a} and {b}", source=f"{a},{b}",
            key=f"coupling:{a}:{b}", score=degree * co,
        ))
        if len(out) >= limit:
            break
    return out
