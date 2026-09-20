from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from torsor_helper import operations as ops
from torsor_helper import render
from torsor_helper.budget import cap_items
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
        lines = [render.recall_hit(h) for h in result.hits]
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
    def clean(apply: bool = False, deep: bool = False) -> str:
        """Reclaim orphaned map notes, dead index rows and journals past retention. Dry run unless apply."""
        stats = ops.clean(store, config, apply=apply, deep=deep)
        verb = "Removed" if apply else "Would remove"
        summary = (
            f"{verb} {stats['map_orphans']} orphaned map note(s), "
            f"{stats['journals_expired']} expired journal(s), "
            f"{stats['dead_rows']} dead index row(s); {stats['reclaimed_bytes']} byte(s)."
        )
        if stats["dry_run"]:
            summary += " Nothing deleted — call again with apply=true to act on this plan."
        return "\n".join([*stats["notes"], summary])

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
    def impact(symbol: str, limit: int = config.budgets.max_items) -> str:
        """Blast radius of a symbol before you change it: which functions/files reference it (run map_repo first). The reported count is the true total; raise limit to list more of them."""
        res = ops.impact(store, config, symbol, limit=limit)
        if res["count"] == 0:
            return f"No references to {symbol!r} found (run map_repo to refresh the symbol graph)."
        lines = [f"- {render.caller(c)}" for c in res["callers"]]
        out = f"{res['count']} reference(s) to {symbol!r}:\n" + "\n".join(lines)
        if res["truncated"]:
            out += f"\n… +{res['truncated']} more (raise limit to list them)"
        return out

    @mcp.tool()
    def connect(source: str, target: str, max_hops: int = config.index.connect_max_hops) -> str:
        """Trace the shortest directed call-graph path from one symbol to another ("how does X reach Y?") — who-calls-what across files (run map_repo first)."""
        res = ops.connect(store, config, source, target, max_hops=max_hops)
        if not res["found"]:
            return (
                f"No call path from {source!r} to {target!r} "
                f"(directed; run map_repo to refresh the symbol graph)."
            )
        chain = render.call_path(res["path"])
        return f"{res['hops']} hop(s) from {source!r} to {target!r}:\n{chain}"

    @mcp.tool()
    def find_files(query: str, mode: str = "fuzzy", limit: int = 20) -> str:
        """Fuzzy, frecency-ranked search over the repo's files and mapped symbols — jump to the right file/symbol fast. mode: fuzzy|literal|regex. Run map_repo first for symbol results."""
        res = ops.find_targets(store, config, query, mode=mode, limit=limit)
        if not res:
            return f"No matches for {query!r}."
        return "\n".join(f"- {render.find_hit(r)}" for r in res)

    @mcp.tool()
    def export() -> str:
        """Export the pyramid to a portable .torsor/llms.txt and a Mermaid module diagram in the map."""
        result = ops.export_project(store, config)
        tail = " + module dependency diagram" if result["diagram"] else ""
        return f"Wrote {result['llms_txt']}{tail}"

    @mcp.tool()
    def get_intent(topic: str = "") -> str:
        """Surface the architecture (patterns, tech, ADRs) and symbols relevant to a topic."""
        return ops.get_intent(store, config, topic or None)

    @mcp.tool()
    def get_rules() -> str:
        """Compact digest of the project's standing constraints (charter principles + ADR rules). Load once per session — cheaper than rediscovering the rules by trial and error."""
        digest = ops.agent_rules(store, config)
        return digest or "No rules declared yet — fill the charter's principles or record ADRs with rules."

    @mcp.tool()
    def recipes(limit: int = 10) -> str:
        """The deterministic torsor lookups called most often — the recurring work to run on the cheap model (see get_model_policy)."""
        recs = ops.recipes(store, limit)
        if not recs:
            return "No recorded operations yet."
        return "\n".join(f"- {render.recipe(r)}" for r in recs)

    @mcp.tool()
    def record_command(name: str, command: str, note: str = "") -> str:
        """Record a project command (test/build/lint/run/deploy) so it's never re-derived. Persisted to the committed command book and shown in the primer."""
        ops.record_command(store, name, command, note)
        return f"Recorded command '{name}': {command}"

    @mcp.tool()
    def list_commands() -> str:
        """The project's recorded commands — run them with your own shell instead of rediscovering how to test/build/lint here."""
        cmds = ops.list_commands(store)
        if not cmds:
            return "No project commands recorded yet (record them with record_command)."
        kept, tail = cap_items(cmds, config.budgets.max_items)
        lines = [f"- {render.command(c, quote=True)}" for c in kept]
        return "\n".join([*lines, tail] if tail else lines)

    @mcp.tool()
    def get_model_policy(as_json: bool = False) -> str:
        """The project's model-routing policy (token thrift): which work belongs on the cheap model vs the smart one. Follow it. as_json returns a form a router can parse."""
        if as_json:
            import json

            return json.dumps(ops.model_policy_json(store, config))
        return ops.model_policy(store, config)

    @mcp.tool()
    def get_primer(max_tokens: int = config.budgets.primer_tokens) -> str:
        """Token-saver: a budgeted project primer (charter + architecture + repo map + token-efficient tool habits). Load once instead of exploring; `torsor primer --write AGENTS.md` makes it free."""
        return ops.project_primer(store, config, max_tokens=max_tokens)

    @mcp.tool()
    def list_practices(language: str = "") -> str:
        """List the curated best-practice pack for a language (python · javascript · typescript · go · rust · agent). Empty language auto-detects from the repo."""
        return ops.list_practices(store, config, language or None)

    @mcp.tool()
    def adopt_practices(language: str) -> str:
        """Adopt a curated best-practice pack: records an ADR whose machine-readable rules `torsor guard` then enforces. Refresh the prompt block after with `torsor rules --write`."""
        result = ops.adopt_practices(store, config, language)
        return result["message"]

    @mcp.tool()
    def record_decision(title: str, context: str, decision: str, consequences: str = "", rules: list[dict] | None = None, supersedes: str | None = None) -> str:
        """Record an Architecture Decision Record. Optional `rules` become drift-guard rules; `supersedes` (an ADR id/slug) marks a prior ADR superseded."""
        path = ops.record_decision(store, title, context, decision, consequences, rules, supersedes)
        return f"Recorded {path}"

    @mcp.tool()
    def check_drift(files: list[str] | None = None, as_json: bool = False, new_only: bool = False) -> str:
        """Flag changes that violate declared architectural intent (ADR rules). Defaults to git-changed files. as_json for machine-readable findings; new_only to exclude baselined (grandfathered) debt."""
        violations = ops.new_drift(store, config, files) if new_only else ops.check_drift(store, config, files)
        if as_json:
            import json

            return json.dumps([v.model_dump() for v in violations])
        if not violations:
            return "No drift from declared intent detected."
        # as_json above is the machine-readable contract and stays whole; this
        # prose path lands in the agent's context, so it is capped.
        kept, tail = cap_items(violations, config.budgets.max_items, more="as_json=true for all")
        lines = [f"- {render.violation(v)}" for v in kept]
        return f"{len(violations)} drift violation(s):\n" + "\n".join([*lines, tail] if tail else lines)

    @mcp.tool()
    def check_dependencies(files: list[str] | None = None) -> str:
        """Flag imports that resolve to no known package — possible hallucinated dependencies (slopsquatting). Offline; defaults to git-changed files."""
        findings = ops.check_dependencies(store, config, files)
        if not findings:
            return "No unknown imports — every import resolves to a known package."
        kept, tail = cap_items(findings, config.budgets.max_items)
        lines = [f"- {render.unknown_import(f)}" for f in kept]
        return (f"{len(findings)} possible hallucinated dependenc(y/ies); verify before installing:\n"
                + "\n".join([*lines, tail] if tail else lines))

    @mcp.tool()
    def verify(files: list[str] | None = None, severity: str | None = None) -> str:
        """The deterministic verification gate (guard + deps + staleness [+ tests]) as
        one machine-checkable verdict — a loop completion condition. Returns JSON
        {ok, exit_code, checks, summary}; each check carries a true `count` and a
        capped `reasons`. Defaults to git-changed files. Static analysis only —
        running the project's recorded commands is CLI-only (`torsor verify
        --run-tests`), the rule that keeps hook installers off this surface too."""
        import json

        return json.dumps(ops.verify(store, config, files, severity=severity))

    @mcp.tool()
    def stale(mark: bool = False) -> str:
        """Flag memory that contradicts current code: dangling [[wikilinks]] and dead
        file-path references. Read-only unless mark=True, which sets status: stale
        on the offending notes (reversible; the body is untouched)."""
        result = ops.check_staleness(store, config, mark=mark)
        findings = result["findings"]
        if not findings:
            return "No staleness detected — memory matches the code."
        kept, tail = cap_items(findings, config.budgets.max_items)
        lines = [f"- {render.staleness(r)}" for r in kept]
        out = f"{len(findings)} staleness finding(s):\n" + "\n".join([*lines, tail] if tail else lines)
        if result["marked"]:
            out += f"\n\nMarked {len(result['marked'])} note(s) status: stale."
        return out

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
        return "\n".join(f"- {render.recommendation(r)}" for r in recs)

    @mcp.tool()
    def hooks_status() -> str:
        """Report which git hooks and Claude Code events carry a torsor auto-capture
        entry. Read-only — installing and removing hooks is CLI-only (`torsor hooks install`)."""
        status = ops.hooks_status(store, config)
        git = "not a git repo" if not status["git_repo"] else ", ".join(
            f"{name}={'on' if on else 'off'}" for name, on in status["git_hooks"].items()
        )
        events = ", ".join(status["claude_events"]) or "none"
        return f"git hooks: {git}\nclaude events: {events}"

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
