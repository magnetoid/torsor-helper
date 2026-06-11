from __future__ import annotations

import re as _re

from torsor_helper import cartographer, db, export as _export, guard
from torsor_helper.coach import mining as coach_mining
from torsor_helper.coach import report as coach_report
from torsor_helper.coach.state import CoachState
from torsor_helper.budget import estimate_tokens, truncate_to_tokens
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.models import Frontmatter, RecallResult
from torsor_helper.recall import keyword_recall
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store

# Fractions of the bootstrap budget allocated per section (must sum to <= 1.0).
_BOOTSTRAP_ALLOC = [
    ("Charter", "charter", 0.30),
    ("System Patterns", "system_patterns", 0.20),
    ("Tech Context", "tech_context", 0.15),
    ("Active Context", "active_context", 0.18),
    ("Progress", "progress", 0.10),
]
_RECENT_JOURNAL_FRACTION = 0.07


def bootstrap_session(store: Store, config: TorsorConfig) -> str:
    cpt = config.budgets.chars_per_token
    total = config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, attr, frac in _BOOTSTRAP_ALLOC:
        path = getattr(store.paths, attr)
        if not path.exists():
            continue
        note = store.read_note(path)
        text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
        if text.strip():
            sections.append(f"## {label}\n\n{text}")

    recent = _recent_journal(store, int(total * _RECENT_JOURNAL_FRACTION), cpt)
    if recent:
        sections.append(f"## Recent Memory\n\n{recent}")

    # Push a short hygiene digest from the Coach (index-free, dismissible).
    digest = coach_report.session_digest(store, limit=3)
    if digest:
        lines = "\n".join(f"- [{rec.severity}] {rec.message}" for rec in digest)
        sections.append(f"## Recommendations\n\n{lines}")

    return "\n\n".join(sections)


def _recent_journal(store: Store, max_tokens: int, cpt: int) -> str:
    if not store.paths.journal_dir.exists():
        return ""
    # Newest day first, so a fresh/sparse latest day still surfaces prior memory.
    journals = sorted(store.paths.journal_dir.glob("*.md"), reverse=True)
    parts: list[str] = []
    used = 0
    for jpath in journals:
        body = store.read_note(jpath).body.strip()
        if not body:
            continue
        cost = estimate_tokens(body, cpt)
        if parts and used + cost > max_tokens:
            break
        parts.append(body)
        used += cost
    return truncate_to_tokens("\n\n".join(parts), max_tokens, cpt)


_EMBEDDER_CACHE: dict = {}


def _embedder_for(config):
    key = (config.embeddings.provider, config.embeddings.model, config.embeddings.dim)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = get_embedder(config)
    return _EMBEDDER_CACHE[key]


def _open_index(store, config):
    """Return a freshly-synced index connection, or None to use keyword fallback."""
    if not config.index.auto_index and not store.paths.index_db.exists():
        return None
    embedder = _embedder_for(config)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, embedder)
    except Exception:
        conn.close()  # don't leak the connection if indexing fails
        raise
    return conn


def recall(store: Store, config: TorsorConfig, query: str, limit: int = 8) -> RecallResult:
    conn = _open_index(store, config)
    if conn is not None:
        try:
            return hybrid_search(
                conn, _embedder_for(config), config, query,
                limit=limit, max_tokens=config.budgets.recall_tokens,
            )
        finally:
            conn.close()
    notes = list(store.iter_notes())
    return keyword_recall(
        notes, query, limit=limit,
        chars_per_token=config.budgets.chars_per_token,
        max_tokens=config.budgets.recall_tokens,
    )


def remember(store: Store, content: str, kind: str = "observation", links: list[str] | None = None) -> str:
    path = store.append_journal(content, kind=kind, links=links or [])
    return str(path)


def update_active(store: Store, focus: str, progress: str, open_questions: str) -> None:
    store.write_note(
        store.paths.active_context,
        Frontmatter(type="active-context", tags=["active"]),
        "Active Context",
        f"## Current focus\n{focus}\n\n## Open questions\n{open_questions}\n",
    )
    store.write_note(
        store.paths.progress,
        Frontmatter(type="progress", tags=["active"]),
        "Progress",
        f"{progress}\n",
    )


def record_handoff(
    store: Store,
    summary: str,
    decisions: str = "",
    open_questions: str = "",
    next_steps: str = "",
) -> str:
    body = (
        f"**Summary:** {summary}\n\n"
        f"**Decisions:** {decisions or '—'}\n\n"
        f"**Open questions:** {open_questions or '—'}\n\n"
        f"**Next steps:** {next_steps or '—'}"
    )
    path = store.append_journal(body, kind="handoff", links=[])
    return str(path)


def map_repo(store: Store, config: TorsorConfig, paths: list[str] | None = None, force: bool = False) -> dict:
    full_scan = paths is None
    fingerprint = cartographer.repo_fingerprint(store.paths.root) if full_scan else None

    conn = db.connect(store.paths.index_db)
    try:
        # Skip the whole scan+render+reindex when the repo is byte-for-byte
        # unchanged since the last full map (a partial `paths` map never skips).
        if full_scan and not force and fingerprint == db.meta_get(conn, "map_fingerprint"):
            return {
                "skipped": True,
                "modules": len(db.modules(conn)),
                "symbols": conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0],
                "edges": conn.execute("SELECT COUNT(*) FROM symbol_edges").fetchone()[0],
            }

        symbols, edges = cartographer.scan_repo_with_edges(store.paths.root, paths)
        rendered = cartographer.render_map(
            symbols,
            overview_tokens=config.budgets.bootstrap_tokens,
            chars_per_token=config.budgets.chars_per_token,
        )
        for relpath, (title, body) in rendered.items():
            target = store.paths.map_dir / relpath
            store.write_note(target, Frontmatter(type="map", status="derived", tags=["map"]), title, body)

        db.replace_all_symbols(conn, symbols)
        db.replace_all_edges(conn, edges)
        reindex(store, conn, _embedder_for(config))
        if full_scan:
            db.meta_set(conn, "map_fingerprint", fingerprint)
        else:
            # A partial map wiped symbols/edges for every other module; clear the
            # fingerprint so the next full map can't falsely skip on an incomplete graph.
            db.meta_set(conn, "map_fingerprint", "")
        conn.commit()
    finally:
        conn.close()

    return {
        "skipped": False,
        "modules": len({s.module for s in symbols}),
        "symbols": len(symbols),
        "edges": len(edges),
    }


def export_project(store: Store, config: TorsorConfig) -> dict:
    return _export.export_project(store, config)


_RULES_START = "<!-- torsor:rules -->"
_RULES_END = "<!-- /torsor:rules -->"


def _charter_section(body: str, heading: str) -> str:
    """Lines under `## <heading>` up to the next H2 (empty string if absent)."""
    match = _re.search(rf"^##\s+{_re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)", body, _re.MULTILINE | _re.DOTALL)
    return match.group(1).strip() if match else ""


def agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int = 600) -> str:
    """A compact, token-budgeted digest of the project's standing constraints —
    charter principles + machine-readable ADR rules — for agent prompt files
    (AGENTS.md / CLAUDE.md). Rules the agent sees at prompt time cost zero
    tool-call tokens per session, and the guard still enforces them in CI."""
    sections: list[str] = []

    if store.paths.charter.exists():
        principles = _charter_section(store.read_note(store.paths.charter).body, "Non-negotiable principles")
        if principles:
            sections.append(f"### Non-negotiable principles\n{principles}")

    rules = guard.load_rules(store)
    if rules:
        lines = []
        for r in rules:
            scope = f" in `{r.scope}`" if r.scope and r.scope != "*.py" else ""
            message = f" — {r.message}" if r.message else ""
            lines.append(f"- {r.kind}: `{r.target}`{scope}{message} (per {r.source})")
        sections.append(
            "### Architecture rules (machine-enforced — `torsor guard` flags violations)\n" + "\n".join(lines)
        )

    if not sections:
        return ""
    digest = "## Project rules (torsor-helper)\n\n" + "\n\n".join(sections)
    return truncate_to_tokens(digest, max_tokens, config.budgets.chars_per_token)


def write_rules_block(store: Store, config: TorsorConfig, target) -> str:
    """Write/refresh the digest as a marker-delimited block in `target`
    (AGENTS.md, CLAUDE.md, …). Idempotent — re-running replaces the block."""
    from pathlib import Path

    digest = agent_rules(store, config)
    block = f"{_RULES_START}\n{digest}\n{_RULES_END}"
    target = Path(target)
    if target.exists():
        text = target.read_text(encoding="utf-8")
        if _RULES_START in text and _RULES_END in text:
            pre, rest = text.split(_RULES_START, 1)
            post = rest.split(_RULES_END, 1)[1]
            new = pre + block + post
        else:
            new = text.rstrip() + "\n\n" + block + "\n"
    else:
        new = block + "\n"
    target.write_text(new, encoding="utf-8")
    return str(target)


def impact(store: Store, config: TorsorConfig, symbol: str) -> dict:
    """Blast radius of a symbol: who references it, across files, via the
    cartographer's resolved reference edges. Read-only over the existing index
    (run `torsor map` first). Empty when the index/symbol is absent."""
    empty = {"symbol": symbol, "callers": [], "count": 0}
    if not store.paths.index_db.exists():
        return empty
    base = symbol.split(".")[-1]
    conn = db.connect(store.paths.index_db)
    try:
        syms = db.search_symbols(conn, base, limit=50)
        exact = [s for s in syms if s.name == symbol]
        matches = exact or [s for s in syms if s.name.split(".")[-1] == base]
        modules = {cartographer.norm_module(s.module) for s in matches}

        callers: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for dotted in modules:
            for caller, module in db.who_references(conn, dotted, base):
                if (caller, module) not in seen:
                    seen.add((caller, module))
                    callers.append({"caller": caller, "module": module})
    finally:
        conn.close()

    callers.sort(key=lambda c: (c["module"], c["caller"]))
    return {"symbol": symbol, "callers": callers, "count": len(callers)}


def get_intent(store: Store, config: TorsorConfig, topic: str | None = None) -> str:
    cpt = config.budgets.chars_per_token
    total = config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, path, frac in [
        ("System Patterns", store.paths.system_patterns, 0.4),
        ("Tech Context", store.paths.tech_context, 0.3),
    ]:
        if path.exists():
            note = store.read_note(path)
            text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
            if text.strip():
                sections.append(f"## {label}\n\n{text}")

    if store.paths.decisions_dir.exists():
        titles = []
        for p in sorted(store.paths.decisions_dir.glob("*.md")):
            note = store.read_note(p)
            if note.frontmatter.status == "superseded":  # stale intent — omit
                continue
            titles.append(note.title)
        if titles:
            sections.append("## Decisions\n\n" + "\n".join(f"- {t}" for t in titles))

    if topic and store.paths.index_db.exists():
        conn = db.connect(store.paths.index_db)
        try:
            syms = db.search_symbols(conn, topic, limit=8)
        finally:
            conn.close()
        if syms:
            lines = [f"- `{s.signature}` ({s.kind}) — {s.module}:{s.line}" for s in syms]
            sections.append("## Relevant existing symbols\n\n" + "\n".join(lines))

    return "\n\n".join(sections)


def _next_adr_number(store) -> int:
    nums = []
    if store.paths.decisions_dir.exists():
        for p in store.paths.decisions_dir.glob("*.md"):
            m = _re.match(r"(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _slug(title: str) -> str:
    s = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "decision"


def _find_adr(store, ref):
    """Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2')."""
    if not store.paths.decisions_dir.exists():
        return None
    ref = str(ref)
    for p in sorted(store.paths.decisions_dir.glob("*.md")):
        if p.stem == ref or p.name == ref or p.stem.startswith(ref + "-"):
            return p
        m = _re.match(r"(\d+)", p.name)
        if m and m.group(1).lstrip("0") == ref.lstrip("0"):
            return p
    return None


def record_decision(store, title, context, decision, consequences="", rules=None, supersedes=None) -> str:
    number = _next_adr_number(store)
    new_stem = f"{number:04d}-{_slug(title)}"

    fm_data = {"type": "decision", "status": "accepted", "tags": ["adr"], "rules": rules or []}
    if supersedes:
        old = _find_adr(store, supersedes)
        if old is not None:
            old_note = store.read_note(old)
            old_data = old_note.frontmatter.model_dump(exclude_none=True)
            old_data["status"] = "superseded"
            old_data["superseded_by"] = new_stem
            store.write_note(old, Frontmatter.model_validate(old_data), old_note.title, old_note.body)
            fm_data["supersedes"] = old.stem

    body = (
        f"## Context\n{context}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    target = store.paths.decisions_dir / f"{new_stem}.md"
    store.write_note(target, Frontmatter.model_validate(fm_data), f"ADR {number:04d}: {title}", body)
    return str(target)


def _git_changed(root) -> list[str]:
    import subprocess
    from pathlib import Path

    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        changed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
        untracked = subprocess.run(
            # --full-name: toplevel-relative like `diff --name-only`, regardless
            # of where inside the repo the torsor root sits
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "--full-name"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    if not toplevel:
        return []
    # git paths are relative to the repo TOPLEVEL, not to the torsor root —
    # re-anchor them (and drop files outside the root) so a .torsor/ living in
    # a subdirectory of the git repo doesn't silently check the wrong paths.
    top, base = Path(toplevel), Path(root).resolve()
    out: list[str] = []
    for f in changed + untracked:
        if not f.endswith(".py"):
            continue
        try:
            out.append((top / f).relative_to(base).as_posix())
        except ValueError:
            continue  # outside the torsor root — not ours to check
    return out


def check_drift(store, config, files=None) -> list:
    if files is None:
        files = _git_changed(store.paths.root)
    return guard.check_drift(store, files)


def new_drift(store, config, files=None) -> list:
    """Drift beyond the committed baseline — the genuinely-new violations."""
    from torsor_helper import baseline as _baseline

    violations = check_drift(store, config, files)
    return _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))


def guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None) -> dict:
    """The single guard orchestration both adapters share: check drift, apply
    the baseline ratchet, and decide strict failure — so the MCP tool and the
    CLI command can't diverge in behavior."""
    from torsor_helper import baseline as _baseline

    violations = check_drift(store, config, files)
    if update_baseline:
        _baseline.save(store.paths.baseline_file, violations)
        return {"violations": violations, "new": [], "baselined": len(violations),
                "failed": False, "updated_baseline": True}
    new = _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))
    failed = bool(strict and guard.strict_failures(new, severity))
    return {"violations": violations, "new": new, "baselined": len(violations) - len(new),
            "failed": failed, "updated_baseline": False}


def check_dependencies(store, config, files=None) -> list:
    """Flag imports that resolve to no known package (possible slopsquatting).
    Defaults to git-changed files; fully offline."""
    from torsor_helper import deps as _deps

    if files is None:
        files = _git_changed(store.paths.root)
    return _deps.unknown_imports(store.paths.root, files)


def recommend(store, config, context=None, limit=8):
    conn = _open_index(store, config)
    embedder = _embedder_for(config) if conn is not None else None
    try:
        return coach_report.assemble(store, config, context=context, limit=limit, conn=conn, embedder=embedder)
    finally:
        if conn is not None:
            conn.close()


def dismiss_recommendation(store, key) -> None:
    state = CoachState(store.paths.index_dir / "coach_state.json")
    state.dismiss(key)
    state.save()


def consolidate(store, config) -> dict:
    written = coach_mining.mine_insights(store)
    duplicates = coach_mining.find_duplicate_entries(store)

    # consolidate is a maintenance pass: index once, directly, so the `indexed`
    # count reflects the freshly-mined insights. (Using _open_index here would
    # reindex internally first, leaving this explicit call to report 0.)
    from torsor_helper.coach import trend as coach_trend

    conn = db.connect(store.paths.index_db)
    try:
        indexed = reindex(store, conn, _embedder_for(config))["indexed"]
        top_accessed = db.top_accessed(conn, limit=3)
        # Snapshot complexity so the Coach can report regressions *since this maintenance pass*.
        db.save_complexity_snapshot(conn, coach_trend.current_complexity(store.paths.root))
    finally:
        conn.close()

    return {
        "insights": len(written),
        "duplicates": len(duplicates),
        "indexed": indexed,
        "top_accessed": top_accessed,
    }
