from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from torsor_helper import db
from torsor_helper.cartographer import DEFAULT_IGNORE

_BOUNDARY = set("/\\._- ")


def _seq_score(query: str, text: str):
    """Greedy subsequence score, or None if `query` is not a subsequence of
    `text`. Rewards consecutive runs and word/path-boundary matches."""
    if not query:
        return 0.0
    smart = query == query.lower()  # smart-case: lowercase query ignores case
    t = text.lower() if smart else text
    q = query.lower() if smart else query
    score = 0.0
    cursor = 0
    prev = -1
    consec = 0
    for qc in q:
        idx = t.find(qc, cursor)
        if idx < 0:
            return None
        at_boundary = (
            idx == 0
            or text[idx - 1] in _BOUNDARY
            or (text[idx].isupper() and text[idx - 1].islower())
        )
        if idx == prev + 1:
            consec += 1
            score += 8 + consec * 2
        else:
            consec = 0
            score += 2
        if at_boundary:
            score += 12
        prev = idx
        cursor = idx + 1
    return score


def fuzzy_score(query: str, text: str):
    """Best fuzzy score across the whole path and its basename (filename matches
    are preferred). None when the query isn't a subsequence of either."""
    full = _seq_score(query, text)
    base = text.rsplit("/", 1)[-1]
    base_s = _seq_score(query, base)
    cands = []
    if full is not None:
        cands.append(full - len(text) * 0.05)          # mild shorter-path preference
    if base_s is not None:
        cands.append(base_s + 25 - len(base) * 0.05)    # strong basename preference
    return max(cands) if cands else None


def _literal_score(query: str, text: str):
    q, t = query.lower(), text.lower()
    idx = t.find(q)
    if idx < 0:
        return None
    base = text.rsplit("/", 1)[-1].lower()
    score = 50.0 - idx * 0.1 - len(text) * 0.05
    if q in base:
        score += 20
        if base.startswith(q):
            score += 15
    return score


def _regex_score(query: str, text: str):
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        return None
    m = pattern.search(text)
    if not m:
        return None
    return 50.0 - m.start() * 0.1 - len(text) * 0.05


def _score(query: str, text: str, mode: str):
    if mode == "literal":
        return _literal_score(query, text)
    if mode == "regex":
        return _regex_score(query, text)
    return fuzzy_score(query, text)


def _git_files(root: Path):
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def _walk_files(root: Path):
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in DEFAULT_IGNORE for part in rel.parts):
            continue
        out.append(rel.as_posix())
    return out


def list_files(root) -> list[str]:
    """Repo files (git-tracked + untracked-not-ignored, or an ignore-filtered
    walk outside git). Always drops DEFAULT_IGNORE dirs (incl. .torsor)."""
    root = Path(root)
    files = _git_files(root)
    if files is None:
        files = _walk_files(root)
    out = [f for f in files if not any(part in DEFAULT_IGNORE for part in Path(f).parts)]
    return sorted(set(out))


def _frecency_boost(entry, clock: int) -> float:
    if not entry or clock <= 0:
        return 1.0
    count, last_seen = entry
    return 1.0 + 0.5 * math.log1p(count) + 0.5 * (last_seen / clock)


def find(store, config, query, *, mode="fuzzy", limit=20, include_files=True, include_symbols=True):
    """Fuzzy/literal/regex search over repo files + mapped symbols, ranked by
    match quality and (for files) frecency. Bumps frecency for returned files."""
    if not query or not query.strip():
        return []
    root = store.paths.root
    conn = db.connect(store.paths.index_db) if store.paths.index_db.exists() else None
    results: list[dict] = []
    try:
        access = db.path_access_map(conn) if conn is not None else {}
        clock = db.find_clock(conn) if conn is not None else 0

        if include_files:
            for f in list_files(root):
                s = _score(query, f, mode)
                if s is None:
                    continue
                results.append({"type": "file", "path": f, "score": s * _frecency_boost(access.get(f), clock)})

        if include_symbols and conn is not None:
            for sym in db.all_symbols(conn):
                s = _score(query, sym["name"], mode)
                if s is None:
                    continue
                results.append({
                    "type": "symbol", "name": sym["name"], "kind": sym["kind"],
                    "module": sym["module"], "line": sym["line"],
                    "score": s * (1.0 + 0.1 * math.log1p(sym["refs"])),
                })

        results.sort(key=lambda r: (-r["score"], r.get("path") or r.get("name")))
        top = results[:limit]
        if conn is not None:
            db.bump_path_access(conn, [r["path"] for r in top if r["type"] == "file"])
    finally:
        if conn is not None:
            conn.close()
    return top
