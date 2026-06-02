from __future__ import annotations

from pathlib import Path

from torsor_helper import db
from torsor_helper.store import Store


def _embedder_identity(embedder) -> str:
    return f"{embedder.name}:{getattr(embedder, 'model', '')}:{embedder.dim}"


def _breadcrumb(note) -> str:
    """A structural situating prefix (tier + path tail + title) for retrieval.

    Contextual-retrieval trick (cf. Anthropic): situating terms like the tier
    name or folder live in a note's *position*, not its prose, so a query for
    them otherwise misses. We index the breadcrumb (embed input + FTS title)
    but never write it into the FTS body, so displayed snippets stay pristine.
    """
    segments = [s for s in Path(note.path).as_posix().split("/") if s][-3:]
    return " ".join([note.tier.name.lower(), *segments, note.title])


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
        breadcrumb = _breadcrumb(note)
        # FTS title carries the breadcrumb (BM25 weights it; body_of never reads
        # it for snippets); body stays byte-identical to the source.
        db.replace_fts(conn, path, breadcrumb, note.body)
        db.replace_edges(conn, path, store.extract_wikilinks(note.body))
        pending.append((path, f"{breadcrumb}\n{note.body}"))  # breadcrumb also situates the embedding

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
