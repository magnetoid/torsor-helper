from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

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


def line_texts(text: str) -> Callable[[Violation], str]:
    """The stripped source line a violation sits on, for `new_violations`."""
    lines = text.splitlines()
    return lambda v: lines[v.line - 1].strip() if 0 < v.line <= len(lines) else ""


def prior_lines(violations, text: str) -> Counter[tuple[tuple[str, str, str], str]]:
    """The (key, line text) of the violations a file had before a change."""
    at = line_texts(text)
    return Counter((_key(v), at(v)) for v in violations)


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


def new_violations(
    violations,
    baseline: dict[tuple[str, str, str], int],
    *,
    line_text: Callable[[Violation], str] | None = None,
    prior: Counter[tuple[tuple[str, str, str], str]] | None = None,
) -> list[Violation]:
    """Violations beyond the baselined count for their (file, rule_kind, target)
    tuple — i.e. the genuinely-new drift. Deterministic (sorted by line).

    The count says HOW MANY are new, not which. Without more to go on the excess
    is the last by line. A caller that knows the file before the change (the edit
    gate) passes `prior`, the (key, line text) of the violations that were already
    there, and `line_text`: the excess is then blamed on lines whose text did not
    violate before, so an addition above an old violation names the new line."""
    grouped: dict[tuple[str, str, str], list[Violation]] = defaultdict(list)
    for v in violations:
        grouped[_key(v)].append(v)
    out: list[Violation] = []
    for key, vs in grouped.items():
        excess = len(vs) - baseline.get(key, 0)
        if excess <= 0:
            continue
        vs_sorted = sorted(vs, key=lambda v: v.line)
        if prior is None or line_text is None:
            out.extend(vs_sorted[-excess:])
            continue
        left = Counter({text: n for (k, text), n in prior.items() if k == key})
        fresh, known = [], []
        for v in vs_sorted:
            text = line_text(v)
            if left[text] > 0:
                left[text] -= 1
                known.append(v)
            else:
                fresh.append(v)
        blamed = (fresh + known[::-1])[:excess]
        out.extend(sorted(blamed, key=lambda v: v.line))
    return out
