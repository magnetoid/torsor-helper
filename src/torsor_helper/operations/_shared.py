"""Index and embedder plumbing shared by every operations submodule.

Infrastructure rather than orchestration: opening a synced index connection,
caching the embedder, and best-effort op logging. Kept in one place so the
embedder cache is a single object — copying it per concern would silently load
the model more than once."""
from __future__ import annotations

from torsor_helper import db
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.store import Store


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


def _log_op(store: Store, op: str, args: str = "") -> None:
    """Best-effort: record a deterministic-tool call for the 'recipes' view. Never
    creates the index just to log, and never raises (logging must not break a tool)."""
    try:
        if not store.paths.index_db.exists():
            return
        conn = db.connect(store.paths.index_db)
        try:
            db.log_op(conn, op, str(args)[:200])
        finally:
            conn.close()
    except Exception:
        pass
