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
    def map_repo(paths: list[str] | None = None) -> str:
        """(Re)generate the repository symbol map and refresh the symbol inventory."""
        stats = ops.map_repo(store, config, paths)
        return f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s)."

    @mcp.tool()
    def get_intent(topic: str = "") -> str:
        """Surface the architecture (patterns, tech, ADRs) and symbols relevant to a topic."""
        return ops.get_intent(store, config, topic or None)

    @mcp.tool()
    def recommend(context: str = "", limit: int = 5) -> str:
        """Health + best-practice recommendations (the Coach). Arrives in Phase 6."""
        return (
            "The Coach (recommendations) lands in Phase 6. Today, use `bootstrap_session` "
            "for context and `recall` to find prior decisions/learnings."
        )

    @mcp.resource("torsor://charter")
    def charter_resource() -> str:
        return paths.charter.read_text(encoding="utf-8") if paths.charter.exists() else ""

    @mcp.resource("torsor://active")
    def active_resource() -> str:
        return paths.active_context.read_text(encoding="utf-8") if paths.active_context.exists() else ""

    return mcp


def run(root: Path | str) -> None:
    build_server(root).run()
