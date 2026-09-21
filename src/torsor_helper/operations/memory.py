"""The memory tier: what an agent reads at session start and writes as it goes.

Every read path here is token-budgeted, and the budget covers what actually
lands in context (see budget.py) — these are the paths an agent pays for on
every single session, so an overrun here is the most expensive kind."""
from __future__ import annotations

from torsor_helper import db, templates
from torsor_helper.budget import cap_items, estimate_tokens, truncate_to_tokens
from torsor_helper.coach import report as coach_report
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter, RecallResult
from torsor_helper.operations._shared import _embedder_for, _log_op, _open_index
from torsor_helper.recall import keyword_recall
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store


# Fractions of the bootstrap budget allocated per section (must sum to <= 1.0).
_BOOTSTRAP_ALLOC = [
    ("Charter", "charter", 0.28),
    ("System Patterns", "system_patterns", 0.18),
    ("Tech Context", "tech_context", 0.13),
    ("Active Context", "active_context", 0.18),
    ("Progress", "progress", 0.09),
]

_RECENT_JOURNAL_FRACTION = 0.06

# The Coach digest is *part of* the budget, not a bonus after it. It used to be
# appended once every allocation was already spent, so the SessionStart digest —
# injected at every start and again after every compaction — overran its ceiling
# on every single session. Allocations above were trimmed to make room.
_COACH_FRACTION = 0.08

def bootstrap_session(store: Store, config: TorsorConfig, *, max_tokens: int | None = None) -> str:
    cpt = config.budgets.chars_per_token
    total = max_tokens or config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, attr, frac in _BOOTSTRAP_ALLOC:
        path = getattr(store.paths, attr)
        if not path.exists() or templates.is_unfilled(store.paths, path):
            continue  # a seed says nothing about the project; the Coach says fill it
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
        # At least its fraction, and whatever the sections above left unused. A
        # fixed 8% cut the most useful line on a fresh project — every section
        # above it empty — to "System patterns is st…".
        used = estimate_tokens("\n\n".join(sections), cpt)
        lines = truncate_to_tokens(
            "\n".join(f"- [{rec.severity}] {rec.message}" for rec in digest),
            max(int(total * _COACH_FRACTION), total - used - 20), cpt,
        )
        if lines.strip():
            sections.append(f"## Recommendations\n\n{lines}")

    # Backstop: the section headings and the joins cost tokens that the
    # per-section fractions never see, so the assembled whole is what has to fit.
    return truncate_to_tokens("\n\n".join(sections), total, cpt)

_SESSION_START_HEADER = (
    "torsor: project memory, {when}. Do NOT call bootstrap_session() — this is it; "
    "reach for recall() / get_intent() / impact() when you need more than this digest.\n\n"
)

def session_start_context(store: Store, config: TorsorConfig, *, how: str = "startup") -> str | None:
    """The digest the Claude Code SessionStart hook injects. Same composition as
    bootstrap_session, under the smaller session_start budget, prefixed with a
    line that stops the agent from spending a tool call re-fetching it. None
    when disabled (config.automation.auto_bootstrap) or when there is nothing
    to say — the adapter then emits nothing, and the session starts untouched."""
    if not config.automation.auto_bootstrap:
        return None
    cpt = config.budgets.chars_per_token
    when = "re-injected after context compaction" if how == "compact" else "injected at session start"
    header = _SESSION_START_HEADER.format(when=when)
    docs = sum(1 for _ in store.iter_doc_paths())
    if docs:
        # The one thing about project docs worth saying every session: that
        # recall reaches them. Their content is recalled on demand, never here.
        header = header.rstrip("\n") + f" recall() also searches {docs} project doc(s) (README, docs/).\n\n"
    # The header lands in context alongside the body, so it is spent from the
    # same ceiling — "a 500-token digest" has to mean the whole injected string.
    body = bootstrap_session(
        store, config,
        max_tokens=max(0, config.budgets.session_start_tokens - estimate_tokens(header, cpt)),
    )
    if not body.strip():
        return None
    return header + body

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

def recall(store: Store, config: TorsorConfig, query: str, limit: int = 8, *,
           type_: str | None = None, kind: str | None = None,
           include_superseded: bool = False, symbol: str | None = None) -> RecallResult:
    """Hybrid search across the pyramid, token-budgeted.

    The filters were implemented in hybrid_search and then dropped here, so no
    adapter could reach them — "only ADRs" and "only learnings" were
    inexpressible despite the plumbing existing. The keyword fallback applies
    them itself, since it has no SQL to push them into."""
    _log_op(store, "recall", query)
    conn = _open_index(store, config)
    if conn is not None:
        try:
            return hybrid_search(
                conn, _embedder_for(config), config, query,
                limit=limit, max_tokens=config.budgets.recall_tokens,
                type_=type_, kind=kind, include_superseded=include_superseded,
                symbol=symbol,
            )
        finally:
            conn.close()
    notes = [n for n in (*store.iter_notes(), *store.iter_docs())
             if _passes(n, type_, kind, include_superseded, symbol)]
    return keyword_recall(
        notes, query, limit=limit,
        chars_per_token=config.budgets.chars_per_token,
        max_tokens=config.budgets.recall_tokens,
    )


def _passes(note, type_: str | None, kind: str | None, include_superseded: bool,
            symbol: str | None = None) -> bool:
    """The same filters hybrid_search applies in SQL, for the no-index path."""
    fm = note.frontmatter
    if type_ is not None and fm.type != type_:
        return False
    if kind is not None and getattr(fm, "kind", None) != kind:
        return False
    if symbol is not None and symbol not in Store.extract_symbol_mentions(note.body):
        return False
    if not include_superseded and fm.type == "decision" and fm.status == "superseded":
        return False
    return True

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

def get_intent(store: Store, config: TorsorConfig, topic: str | None = None) -> str:
    _log_op(store, "get_intent", topic or "")
    cpt = config.budgets.chars_per_token
    total = config.budgets.intent_tokens
    sections: list[str] = []

    for label, path, frac in [
        ("System Patterns", store.paths.system_patterns, 0.4),
        ("Tech Context", store.paths.tech_context, 0.3),
    ]:
        if path.exists() and not templates.is_unfilled(store.paths, path):
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
            # ADR titles grow without bound; the count of the hidden ones is the
            # part the agent actually needs (it says whether to go look).
            kept, tail = cap_items(titles, config.budgets.max_items,
                                   more="read .torsor/architecture/decisions/")
            body = "\n".join(f"- {t}" for t in kept)
            sections.append("## Decisions\n\n" + body + (f"\n{tail}" if tail else ""))

    if topic and store.paths.index_db.exists():
        conn = db.connect(store.paths.index_db)
        try:
            syms = db.search_symbols(conn, topic, limit=8)
            # The memory half of the same question. `Decisions` above lists every
            # ADR title regardless of topic; this is what was written down about
            # *this* symbol specifically, including journals, which never reach
            # that list.
            base = topic.split(".")[-1]
            mention_paths: list[str] = []
            for spelling in dict.fromkeys((topic, base)):
                # not `path`: that name is a Path in the section loop above, and
                # reusing it here is how a str quietly ends up in a Path slot.
                for note_path in db.notes_mentioning(conn, spelling):
                    if note_path not in mention_paths:
                        mention_paths.append(note_path)
            rows = db.note_rows(conn, mention_paths)
        finally:
            conn.close()
        if syms:
            lines = [f"- `{s.signature}` ({s.kind}) — {s.module}:{s.line}" for s in syms]
            sections.append("## Relevant existing symbols\n\n" + "\n".join(lines))
        if mention_paths:
            kept, tail = cap_items(mention_paths, config.budgets.max_items,
                                   more=f"recall --symbol {base}")
            lines = [
                f"- {(rows.get(np) or {}).get('title') or np} "
                f"[{(rows.get(np) or {}).get('type') or 'note'}]"
                for np in kept
            ]
            body = "\n".join(lines) + (f"\n{tail}" if tail else "")
            sections.append(f"## Recorded about `{base}`\n\n" + body)

    return truncate_to_tokens("\n\n".join(sections), total, cpt)
