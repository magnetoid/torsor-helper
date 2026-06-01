from __future__ import annotations

from torsor_helper import db
from torsor_helper.store import Store


def reindex(store: Store, conn, embedder, *, full: bool = False) -> dict:
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

    conn.commit()
    return {"indexed": len(pending), "deleted": deleted, "total": len(seen)}
