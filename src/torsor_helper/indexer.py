from __future__ import annotations

from torsor_helper import db
from torsor_helper.store import Store


def _embedder_identity(embedder) -> str:
    return f"{embedder.name}:{getattr(embedder, 'model', '')}:{embedder.dim}"


def reindex(store: Store, conn, embedder, *, full: bool = False) -> dict:
    # If the embedder (name/model/dim) changed since the last build, the stored
    # vectors live in a different space — force a full re-embed so cosine search
    # stays valid (and never mixes dimensions).
    identity = _embedder_identity(embedder)
    if db.meta_get(conn, "embedder") not in (None, identity):
        full = True

    existing = db.note_hashes(conn)
    seen: set[str] = set()
    pending: list[tuple[str, str]] = []  # (path, body) to embed

    for note in store.iter_notes():
        path = str(note.path)
        seen.add(path)
        if not full and existing.get(path) == note.content_hash:
            continue
        kind = getattr(note.frontmatter, "kind", None)
        db.upsert_note(
            conn, path, note.content_hash, int(note.tier),
            note.frontmatter.type, kind, note.title, note.frontmatter.updated or "",
        )
        db.replace_fts(conn, path, note.title, note.body)
        db.replace_edges(conn, path, store.extract_wikilinks(note.body))
        pending.append((path, note.body))

    if pending:
        vectors = embedder.embed([body for _, body in pending])
        for (path, _), vec in zip(pending, vectors):
            db.upsert_vector(conn, path, vec)

    deleted = 0
    for path in list(existing):
        if path not in seen:
            db.delete_note(conn, path)
            deleted += 1

    db.meta_set(conn, "embedder", identity)
    conn.commit()
    return {"indexed": len(pending), "deleted": deleted, "total": len(seen)}
