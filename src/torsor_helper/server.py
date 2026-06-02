from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from torsor_helper import operations as ops
from torsor_helper.config import load_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def build_server(root: Path | str) -> FastMCP:
    paths = TorsorPaths(Path(root))
    store = Store(paths)
    config = load_config(paths)

    mcp = FastMCP("torsor-helper")

    @mcp.tool()
    def bootstrap_session() -> str:
        """Return a budgeted summary of the whole pyramid for session start."""
        return ops.bootstrap_session(store, config)

    @mcp.tool()
    def recall(query: str, limit: int = 8) -> str:
        """Hybrid keyword search across memory, wiki and map. Returns ranked snippets."""
        result = ops.recall(store, config, query, limit=limit)
        if not result.hits:
            return f"No matches for: {query!r}"
        lines = [f"### {h.title} ({h.tier.name})\n{h.snippet}" for h in result.hits]
        return "\n\n".join(lines)

    @mcp.tool()
    def remember(content: str, kind: str = "observation", links: list[str] | None = None) -> str:
        """Persist an observation/decision/learning to episodic memory."""
        return ops.remember(store, content, kind=kind, links=links)

    @mcp.tool()
    def update_active(focus: str, progress: str, open_questions: str) -> str:
        """Update the active working state (current focus, progress, open questions)."""
        ops.update_active(store, focus, progress, open_questions)
        return "active context updated"

    @mcp.tool()
    def handoff(summary: str, decisions: str = "", open_questions: str = "", next_steps: str = "") -> str:
        """Write a structured end-of-session handoff that the next session resumes from."""
        return ops.record_handoff(store, summary, decisions, open_questions, next_steps)

    @mcp.tool()
    def map_repo(paths: list[str] | None = None, force: bool = False) -> str:
        """(Re)generate the repository symbol map and refresh the symbol inventory. Skips when unchanged unless force."""
        stats = ops.map_repo(store, config, paths, force=force)
        if stats.get("skipped"):
            return f"Map already up to date ({stats['symbols']} symbol(s), {stats['modules']} module(s))."
        return (
            f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s) "
            f"({stats['edges']} reference edge(s))."
        )

    @mcp.tool()
    def get_intent(topic: str = "") -> str:
        """Surface the architecture (patterns, tech, ADRs) and symbols relevant to a topic."""
        return ops.get_intent(store, config, topic or None)

    @mcp.tool()
    def record_decision(title: str, context: str, decision: str, consequences: str = "", rules: list[dict] | None = None) -> str:
        """Record an Architecture Decision Record. Optional `rules` become drift-guard rules."""
        path = ops.record_decision(store, title, context, decision, consequences, rules)
        return f"Recorded {path}"

    @mcp.tool()
    def check_drift(files: list[str] | None = None) -> str:
        """Flag changes that violate declared architectural intent (ADR rules). Defaults to git-changed files."""
        violations = ops.check_drift(store, config, files)
        if not violations:
            return "No drift from declared intent detected."
        lines = [f"- {v.file}:{v.line} — {v.message} (per {v.source})" for v in violations]
        return f"{len(violations)} drift violation(s):\n" + "\n".join(lines)

    @mcp.tool()
    def consolidate() -> str:
        """Self-improving maintenance: mine journal entries into insight notes, reindex, report duplicates."""
        stats = ops.consolidate(store, config)
        msg = (
            f"Mined {stats['insights']} insight file(s); reindexed {stats['indexed']} note(s); "
            f"found {stats['duplicates']} duplicate entr(y/ies)."
        )
        if stats["top_accessed"]:
            hot = ", ".join(f"{path} ({n}x)" for path, n in stats["top_accessed"])
            msg += f"\nMost-recalled: {hot}"
        return msg

    @mcp.tool()
    def recommend(context: str = "", limit: int = 8) -> str:
        """Health + best-practice recommendations (the Coach). Pass a context (e.g. what you're about to build) for reuse hints."""
        recs = ops.recommend(store, config, context or None, limit=limit)
        if not recs:
            return "No recommendations right now — the project looks healthy."
        lines = []
        for r in recs:
            tail = f" → {r.action}" if r.action else ""
            lines.append(f"- [{r.severity}/{r.kind}] {r.message}{tail}  (key: {r.key})")
        return "\n".join(lines)

    @mcp.resource("torsor://charter")
    def charter_resource() -> str:
        return paths.charter.read_text(encoding="utf-8") if paths.charter.exists() else ""

    @mcp.resource("torsor://active")
    def active_resource() -> str:
        return paths.active_context.read_text(encoding="utf-8") if paths.active_context.exists() else ""

    return mcp


def run(root: Path | str, transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the MCP server. transport "stdio" (default) for a local agent, or
    "streamable-http" to serve over HTTP (shared/team/remote use)."""
    mcp = build_server(root)
    if transport != "stdio":
        mcp.settings.host = host
        mcp.settings.port = port
    mcp.run(transport=transport)
