from __future__ import annotations

import warnings
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

    # If the index *format* changed since this DB was last built (e.g. what goes
    # into the FTS title or the embedding input), unchanged content hashes would
    # keep stale rows forever — force one full rebuild per schema bump.
    if db.meta_get(conn, "indexed_schema") != str(db.SCHEMA_VERSION):
        full = True

    existing = db.note_stats(conn)
    seen: set[str] = set()
    pending: list[tuple[str, str]] = []  # (path, body) to embed

    for md in store.iter_note_paths():
        path = str(md)
        seen.add(path)
        try:
            st = md.stat()
        except OSError:
            continue
        row = existing.get(path)
        # Stat pre-screen: an unchanged (mtime, size) means an unchanged file —
        # skip the read + YAML parse + hash entirely. At a few thousand notes
        # this is the difference between O(stat) and O(read+parse) per recall.
        if not full and row and row["mtime_ns"] == st.st_mtime_ns and row["size"] == st.st_size:
            continue
        try:
            note = store.read_note(md)
        except (OSError, UnicodeDecodeError) as exc:
            warnings.warn(f"skipping unreadable note {md}: {exc}")
            continue
        if not full and row and row["content_hash"] == note.content_hash:
            # touched but identical (e.g. rewrite of the same content): refresh
            # the stat columns so the pre-screen works next time, skip re-embed
            db.update_note_stat(conn, path, st.st_mtime_ns, st.st_size)
            continue
        kind = getattr(note.frontmatter, "kind", None)
        db.upsert_note(
            conn, path, note.content_hash, int(note.tier),
            note.frontmatter.type, kind, note.title, note.frontmatter.updated or "",
            note.frontmatter.status, mtime_ns=st.st_mtime_ns, size=st.st_size,
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

    # Heal wikilink edges whose target was indexed after the linking note
    # (insert-order dependence) or has been deleted since.
    db.reresolve_edges(conn)

    db.meta_set(conn, "embedder", identity)
    db.meta_set(conn, "indexed_schema", str(db.SCHEMA_VERSION))
    conn.commit()
    return {"indexed": len(pending), "deleted": deleted, "total": len(seen)}
