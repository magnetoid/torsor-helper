from __future__ import annotations

from pathlib import Path

from torsor_helper import db
from torsor_helper.cartographer import iter_source_files
from torsor_helper.coach.hotspots import _complexity
from torsor_helper.models import Recommendation


def current_complexity(root: Path) -> dict[str, int]:
    """Per-file complexity for every source file (reuses the hotspot proxy)."""
    root = Path(root)
    out: dict[str, int] = {}
    for p in iter_source_files(root):
        c = _complexity(p)
        if c > 0:
            out[p.relative_to(root).as_posix()] = c
    return out


def find_regressions(root: Path, conn, rel: float = 0.25, abs_min: int = 5, limit: int = 5) -> list[Recommendation]:
    """'New findings only': files whose complexity rose meaningfully since the
    last snapshot (≥ abs_min absolute AND ≥ rel relative). Empty until a baseline
    exists (written by `consolidate`), so a clean project never nags. Deterministic."""
    snapshot = db.load_complexity_snapshot(conn)
    if not snapshot:
        return []
    current = current_complexity(root)
    out: list[Recommendation] = []
    for f, now in current.items():
        before = snapshot.get(f)
        if before is None:  # new file — covered by hotspots, not a regression-since-baseline
            continue
        delta = now - before
        if delta >= abs_min and now >= before * (1.0 + rel):
            out.append(Recommendation(
                kind="regression", severity="suggest",
                message=(
                    f"{f} complexity rose {before}→{now} (+{delta}) since the last snapshot — "
                    f"review before it ossifies."
                ),
                action=f"review {f}", source=f, key=f"regression:{f}", score=float(delta),
            ))
    out.sort(key=lambda r: (-r.score, r.key))
    return out[:limit]
