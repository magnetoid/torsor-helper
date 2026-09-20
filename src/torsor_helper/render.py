"""How one result item reads, in one place.

The CLI and the MCP server rendered the same eleven things independently, and
they had already drifted — the same caller list, violation or staleness finding
came out slightly different depending on which surface asked. The Coach saw the
consequence before anyone else did: cli.py and server.py changed together in 84%
of commits while neither imports the other.

These functions return the *content* of a line and nothing else. Framing stays
with the adapter, because the two genuinely differ: the server bullets items
with "- " so they read as a list inside a tool result, while the CLI indents
with two spaces under a heading it already printed. Unifying that would make
one of them worse, so the split is deliberate — what must not drift is the part
a reader parses.

Core module: no adapter imports, no I/O, no config. Pure functions over the
result shapes operations returns.
"""
from __future__ import annotations


def caller(entry) -> str:
    """One row of an impact result: where a reference lives."""
    return f"{entry['module']} :: {entry['caller']}"


def find_hit(entry) -> str:
    """One row of a find result — a file path, or a mapped symbol with its site."""
    if entry["type"] == "file":
        return entry["path"]
    return f"{entry['module']}:{entry['line']}  {entry['name']} ({entry['kind']})"


def call_path(path, *, arrow: str = "->") -> str:
    """A connect result: the chain of symbols from source to target."""
    return f" {arrow} ".join(f"{step['symbol']} ({step['module']})" for step in path)


def violation(v) -> str:
    """One drift finding, with the ADR that declared the rule it broke."""
    return f"{v.file}:{v.line} — [{v.severity}] {v.message} (per {v.source})"


def unknown_import(finding) -> str:
    """One possible phantom dependency."""
    return f"{finding['file']}:{finding['line']} — unknown import '{finding['name']}'"


def staleness(finding) -> str:
    """One piece of memory that no longer matches the code."""
    return f"[{finding.kind}] {finding.message}"


def recommendation(rec, *, arrow: str = "→") -> str:
    """One Coach recommendation, including the key needed to dismiss it."""
    tail = f" {arrow} {rec.action}" if rec.action else ""
    return f"[{rec.severity}/{rec.kind}] {rec.message}{tail}  (key: {rec.key})"


def command(entry, *, quote: bool = False) -> str:
    """One entry from the learned command book."""
    cmd = f"`{entry['command']}`" if quote else entry["command"]
    note = f" — {entry['note']}" if entry["note"] else ""
    return f"{entry['name']}: {cmd}{note}"


def recipe(entry) -> str:
    """One row of the op-frequency log: a lookup worth routing to a cheap model."""
    args = f" {entry['args']!r}" if entry["args"] else ""
    return f"{entry['hits']}× {entry['op']}{args}"


def recall_hit(hit) -> str:
    """One recall result as it lands in an agent's context. budget.hit_cost bills
    exactly this shape, so the two must change together."""
    return f"### {hit.title} ({hit.tier.name})\n{hit.snippet}"
