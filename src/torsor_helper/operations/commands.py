"""The learned command book and the op-frequency log.

Recording a project's commands once, so no session re-derives how to test or
build it, and surfacing which deterministic lookups recur. Executing a recorded
command is deliberately reachable only from the CLI (ADR 0009's footgun rule):
the string comes out of a git-committed file and runs through a shell."""
from __future__ import annotations

import re as _re
import subprocess

from torsor_helper import db
from torsor_helper.models import Frontmatter
from torsor_helper.store import Store


_CMD_RE = _re.compile(r"^- \*\*(.+?)\*\*:\s*`([^`]+)`(?:\s*—\s*(.*))?$")

def list_commands(store: Store) -> list[dict]:
    """The recorded project commands, parsed from .torsor/commands.md."""
    if not store.paths.commands_file.exists():
        return []
    out: list[dict] = []
    for line in store.read_note(store.paths.commands_file).body.splitlines():
        m = _CMD_RE.match(line.strip())
        if m:
            out.append({"name": m.group(1).strip(), "command": m.group(2).strip(), "note": (m.group(3) or "").strip()})
    return out

def record_command(store: Store, name: str, command: str, note: str = "") -> str:
    """Record/update a named project command so it's never re-derived. Persists to
    the committed Markdown command book; surfaces in the primer."""
    cmds = {c["name"]: c for c in list_commands(store)}
    cmds[name] = {"name": name, "command": command, "note": note}
    lines = []
    for n in sorted(cmds):
        c = cmds[n]
        line = f"- **{c['name']}**: `{c['command']}`"
        if c["note"]:
            line += f" — {c['note']}"
        lines.append(line)
    store.write_note(
        store.paths.commands_file,
        Frontmatter(type="commands", tags=["commands"]),
        "Project Commands", "\n".join(lines),
    )
    return str(store.paths.commands_file)

def run_command(store: Store, name: str):
    """Execute a recorded command (returns CompletedProcess, or None if unknown).
    Runs the user-/agent-recorded command via the shell from the repo root."""
    cmds = {c["name"]: c for c in list_commands(store)}
    found = cmds.get(name)
    if not found:
        return None
    return subprocess.run(found["command"], shell=True, cwd=str(store.paths.root))

def recipes(store: Store, limit: int = 10) -> list:
    """The most-repeated deterministic lookups — what the agent does over and over,
    i.e. prime candidates to run on the cheap model."""
    if not store.paths.index_db.exists():
        return []
    conn = db.connect(store.paths.index_db)
    try:
        return db.top_ops(conn, limit)
    finally:
        conn.close()
