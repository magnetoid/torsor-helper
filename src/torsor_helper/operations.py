from __future__ import annotations

from torsor_helper import db
from torsor_helper.budget import truncate_to_tokens
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

    return "\n\n".join(sections)


def _recent_journal(store: Store, max_tokens: int, cpt: int) -> str:
    journals = sorted(store.paths.journal_dir.glob("*.md")) if store.paths.journal_dir.exists() else []
    if not journals:
        return ""
    latest = store.read_note(journals[-1])
    return truncate_to_tokens(latest.body.strip(), max_tokens, cpt)


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
