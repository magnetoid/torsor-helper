from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from torsor_helper.models import Violation

# The baseline grandfathers pre-existing drift so `--strict` fails only when a
# file's violation COUNT per (file, rule_kind, target) grows — no fuzzy
# snippet-hash (which could let a genuinely-new violation silently inherit an
# old hash). Count semantics mean fixing one grandfathered violation frees a
# slot for a new one of the same kind in the same file (ADR 0005 trade-off).
# It lives at .torsor/baseline.json: committed, reviewable config, NOT under
# the disposable .index/. Only `--update-baseline` writes it.


def _key(v: Violation) -> tuple[str, str, str]:
    return (v.file, v.rule_kind, v.target)


def load(path: Path) -> dict[tuple[str, str, str], int]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[tuple[str, str, str], int] = {}
    for entry in data.get("violations", []):
        try:
            out[(entry["file"], entry["rule_kind"], entry["target"])] = int(entry["count"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save(path: Path, violations) -> None:
    path = Path(path)
    counts = Counter(_key(v) for v in violations)
    entries = [
        {"file": f, "rule_kind": rk, "target": t, "count": n}
        for (f, rk, t), n in sorted(counts.items())
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"violations": entries}, indent=2) + "\n", encoding="utf-8")


def new_violations(violations, baseline: dict[tuple[str, str, str], int]) -> list[Violation]:
    """Violations beyond the baselined count for their (file, rule_kind, target)
    tuple — i.e. the genuinely-new drift. Deterministic (sorted by line)."""
    grouped: dict[tuple[str, str, str], list[Violation]] = defaultdict(list)
    for v in violations:
        grouped[_key(v)].append(v)
    out: list[Violation] = []
    for key, vs in grouped.items():
        allowed = baseline.get(key, 0)
        if len(vs) > allowed:
            vs_sorted = sorted(vs, key=lambda v: v.line)
            out.extend(vs_sorted[allowed:])
    return out
