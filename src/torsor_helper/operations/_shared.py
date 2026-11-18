"""Index and embedder plumbing shared by every operations submodule.

Infrastructure rather than orchestration: opening a synced index connection,
caching the embedder, and best-effort op logging. Kept in one place so the
embedder cache is a single object — copying it per concern would silently load
the model more than once."""
from __future__ import annotations

import threading

from torsor_helper import db
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex


_EMBEDDER_CACHE: dict = {}
# Held across the load, so a recall that arrives while the start-up warm-up is
# still loading the model waits for it rather than loading a second copy.
_EMBEDDER_LOCK = threading.Lock()


def _embedder_for(config):
    key = (config.embeddings.provider, config.embeddings.model, config.embeddings.dim)
    with _EMBEDDER_LOCK:
        if key not in _EMBEDDER_CACHE:
            _EMBEDDER_CACHE[key] = get_embedder(config)
        return _EMBEDDER_CACHE[key]


def start_embedder_warmup(paths) -> threading.Thread | None:
    """Load the configured embedder on a daemon thread; None when there is nothing to load.

    Importing fastembed and loading its model costs 1.6-2.4 s per process, and
    it used to land on the agent's first recall. The MCP server starts before
    the agent's first turn and the first recall comes turns later, so the load
    runs in that gap. The hashing embedder costs nothing to build, and a
    project that is missing or misconfigured is left for the tools to report."""
    from torsor_helper.config import load_config

    if not paths.base.exists():
        return None
    try:
        config = load_config(paths)
    except Exception:  # noqa: BLE001 - every tool call reports it; the warm-up stays quiet
        return None
    if config.embeddings.provider != "fastembed":
        return None
    thread = threading.Thread(target=_embedder_for, args=(config,), name="torsor-embedder-warmup",
                              daemon=True)
    thread.start()
    return thread


def _open_index(store, config):
    """Return a freshly-synced index connection, or None to use keyword fallback."""
    if not config.index.auto_index:
        # It used to also require the DB to be absent, so the setting worked
        # exactly once — on a virgin project. After the first recall built an
        # index, every later recall reindexed regardless. Serve what is there.
        if not store.paths.index_db.exists():
            return None
        return db.connect(store.paths.index_db)
    embedder = _embedder_for(config)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, embedder)
    except Exception:
        conn.close()  # don't leak the connection if indexing fails
        raise
    return conn

