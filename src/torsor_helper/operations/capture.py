"""Auto-capture: memory that writes itself on the git and agent lifecycle.

Deterministic and offline — the handoff digest is composed from git log/diff,
the op-log delta and new ADRs, never from a model. Every entry point checks its
`automation` flag first, so any single behaviour can be disabled in torsor.toml
without uninstalling the hooks."""
from __future__ import annotations

import json
import re as _re
from pathlib import Path

from torsor_helper import db, gitinfo
from torsor_helper.operations._state import _state_file
from torsor_helper.operations.decisions import _next_adr_number
from torsor_helper.operations.graph import map_repo
from torsor_helper.operations.maintenance import _snapshot_complexity
from torsor_helper.operations.memory import record_handoff


def _capture_state_path(store):
    # The auto-handoff watermark: a git HEAD plus op counters. Machine-local, but
    # NOT derivable — losing it makes the next handoff replay the whole history —
    # so it lives in state/, not in the index `clean --deep` throws away.
    return _state_file(store, "capture_state.json")

def _load_capture_state(store) -> dict:
    try:
        data = json.loads(_capture_state_path(store).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def _save_capture_state(store, data: dict) -> None:
    path = _capture_state_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _op_totals(store) -> dict:
    if not store.paths.index_db.exists():
        return {}
    conn = db.connect(store.paths.index_db)
    try:
        return db.op_totals(conn)
    finally:
        conn.close()

def _op_delta(store, snapshot: dict) -> list[tuple[str, int]]:
    """Per-op hit increase since the last snapshot — a best-effort, deterministic
    'what ran this session' (op_log is aggregate, not session-scoped: db.py)."""
    cur = _op_totals(store)
    out = [(op, cur[op] - int(snapshot.get(op, 0))) for op in cur]
    out = [(op, n) for op, n in out if n > 0]
    out.sort(key=lambda t: (-t[1], t[0]))
    return out

def _adrs_between(store, prev: int, cur: int) -> list[str]:
    if cur <= prev or not store.paths.decisions_dir.exists():
        return []
    out = []
    for p in sorted(store.paths.decisions_dir.glob("*.md")):
        m = _re.match(r"(\d+)", p.name)
        if m and prev < int(m.group(1)) <= cur:
            out.append(p.stem)
    return out

def _read_md_section(text: str, header: str) -> str:
    """Body under a `## header` up to the next `## ` (or EOF). Empty when absent."""
    m = _re.search(rf"(?m)^##\s+{_re.escape(header)}\s*$", text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = _re.search(r"(?m)^##\s+", rest)
    return (rest[: nxt.start()] if nxt else rest).strip()

def _find_file_paths(obj) -> list[str]:
    """Recursively collect `file_path` string values from a parsed transcript
    event — generic so a Claude Code schema tweak can't break it."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "file_path" and isinstance(v, str):
                found.append(v)
            else:
                found.extend(_find_file_paths(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_file_paths(item))
    return found

def _transcript_digest(transcript_path) -> str:
    try:
        raw = Path(transcript_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    files: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for fp in _find_file_paths(event):
            if fp not in files:
                files.append(fp)
    if not files:
        return ""
    return "Files touched this session:\n" + "\n".join(f"- {f}" for f in files[:20])

def auto_handoff(store, config, *, session_id=None, transcript_path=None) -> str | None:
    """Write a deterministic end-of-session handoff (no LLM) from git history +
    the op-log delta + new ADRs + the agent's own active-context/progress, so the
    agent never has to call handoff() by hand. Writes nothing (returns None) when
    disabled or when nothing changed — avoids empty handoffs."""
    if not config.automation.auto_handoff:
        return None
    root = store.paths.root
    state = _load_capture_state(store)
    last_head = state.get("last_head") or ""
    head = gitinfo.head(root)

    commit_lines: list[str] = []
    diffstat = ""
    if head and last_head and last_head != head:
        log = gitinfo.output(root, "log", "--oneline", f"{last_head}..{head}")
        commit_lines = [ln for ln in log.splitlines() if ln.strip()]
        diffstat = gitinfo.output(root, "diff", "--shortstat", f"{last_head}..{head}")
    worktree = gitinfo.changed_source_files(root)
    worktree_stat = gitinfo.output(root, "diff", "--shortstat")
    op_delta = _op_delta(store, state.get("op_snapshot") or {})
    prev_adr = int(state.get("adr_max") or 0)
    cur_adr = _next_adr_number(store) - 1
    new_adrs = _adrs_between(store, prev_adr, cur_adr)

    if not commit_lines and not worktree and not op_delta and not new_adrs:
        return None

    bits: list[str] = []
    if commit_lines:
        bits.append(f"{len(commit_lines)} commit(s)")
    if diffstat:
        bits.append(diffstat)
    elif worktree_stat:
        bits.append(f"uncommitted: {worktree_stat}")
    if op_delta:
        bits.append("ran " + ", ".join(f"{n}× {op}" for op, n in op_delta))
    summary = "; ".join(bits) or "session activity"
    if commit_lines:
        summary += "\n\nCommits:\n" + "\n".join(f"- {c}" for c in commit_lines[:20])
    if config.automation.parse_transcript and transcript_path:
        extra = _transcript_digest(transcript_path)
        if extra:
            summary += f"\n\n{extra}"

    active_text = store.read_note(store.paths.active_context).body if store.paths.active_context.exists() else ""
    open_qs = _read_md_section(active_text, "Open questions")
    next_steps = store.read_note(store.paths.progress).body.strip() if store.paths.progress.exists() else ""

    path = record_handoff(store, summary, decisions=", ".join(new_adrs),
                          open_questions=open_qs, next_steps=next_steps)

    _save_capture_state(store, {
        "last_head": head or last_head,
        "op_snapshot": _op_totals(store),
        "adr_max": cur_adr,
    })
    return path

def on_commit(store, config) -> dict:
    """Post-commit hook core: partial-map the just-committed source files (the
    ADR 0008 merge — zero new mapping code) and refresh the complexity baseline,
    so the graph and regression signal stay fresh with no manual map/consolidate.
    Best-effort; writes only .torsor/ Markdown + the disposable index, never commits."""
    result = {"mapped": [], "snapshot": False}
    changed = gitinfo.commit_source_files(store.paths.root, "HEAD")
    if not changed:
        return result
    if config.automation.auto_map_on_commit:
        map_repo(store, config, paths=changed)
        result["mapped"] = changed
    if config.automation.auto_snapshot_on_commit:
        _snapshot_complexity(store)
        result["snapshot"] = store.paths.index_db.exists()
    return result
