from __future__ import annotations

import warnings
from pathlib import Path

from torsor_helper import db, templates
from torsor_helper.models import Tier
from torsor_helper.store import Store


# What goes INTO the index — the breadcrumb, the FTS title, the embedding
# input. Bump this only when that changes, because it forces every note to be
# re-embedded. It is deliberately not db.SCHEMA_VERSION: that governs the DDL,
# and adding a secondary index or a lookup table has no bearing on whether a
# stored vector is still valid. Tying the two meant a pure-DDL change re-embedded
# the whole corpus.
INDEX_FORMAT_VERSION = 2

# The note -> symbol mention table (db.note_symbols) separately, because it is
# derived from a note's body WITHOUT touching the breadcrumb, the FTS title or
# the embedding input. Bumping INDEX_FORMAT_VERSION would have worked and would
# have re-embedded the whole corpus to populate a regex result; this backfills
# it by reading each note once. Bump when the extraction rule changes.
MENTIONS_FORMAT_VERSION = 1


def _is_fallback(stored: str | None, embedder) -> bool:
    """True when this run is the hashing fallback standing in for the embedder
    that actually built the index. Not a configuration change — an outage."""
    return stored is not None and not stored.startswith("hashing:") and embedder.name == "hashing"


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


def _indexable(store: Store):
    """(path, reader) for everything the index covers: torsor's own notes, then
    the project's docs, each read the way its tier needs."""
    for md in store.iter_note_paths():
        yield md, store.read_note
    for md in store.iter_doc_paths():
        yield md, store.read_doc


def _backfill_mentions(store: Store, conn, *, skip) -> None:
    """Fill db.note_symbols for notes this run did not re-read. Reads and parses
    each one; deliberately does not embed, which is the whole point of keeping
    this stamp separate from INDEX_FORMAT_VERSION."""
    done = set(skip)
    for md, read in _indexable(store):
        path = md.as_posix()
        if path in done:
            continue
        try:
            note = read(md)
        except (OSError, UnicodeDecodeError):
            continue
        mentions = [] if note.tier is Tier.MAP else store.extract_symbol_mentions(note.body)
        db.replace_note_symbols(conn, path, mentions)


def reindex(store: Store, conn, embedder, *, full: bool = False) -> dict:
    # If the embedder (name/model/dim) changed since the last build, the stored
    # vectors live in a different space — force a full re-embed so cosine search
    # stays valid (and never mixes dimensions).
    identity = _embedder_identity(embedder)
    stored = db.meta_get(conn, "embedder")
    embedder_matches = stored in (None, identity)
    if not embedder_matches and _is_fallback(stored, embedder):
        # get_embedder falls back to hashing whenever fastembed raises —
        # including a first-run model download with no network. Treating that
        # as an embedder change re-embedded the whole corpus, and the recovery
        # re-embedded it back. Leave the good vectors alone: text indexing
        # continues and search skips the vector leg while the spaces disagree
        # (db.vectors_match). Same rule as "no index -> keyword recall".
        #
        # A real change — a different dim, or fastembed newly installed — is not
        # a fallback and still rebuilds, which is what the user asked for.
        pass
    elif not embedder_matches:
        full = True
        embedder_matches = True

    # If the index *format* changed since this DB was last built (e.g. what goes
    # into the FTS title or the embedding input), unchanged content hashes would
    # keep stale rows forever — force one full rebuild per format bump.
    if db.meta_get(conn, "indexed_format") != str(INDEX_FORMAT_VERSION):
        full = True

    existing = db.note_stats(conn)
    seeds = set(templates.seed_files(store.paths))  # a handful of paths; checked per note
    seen: set[str] = set()
    slug_index = None
    pending: list[tuple[str, str]] = []  # (path, body) to embed

    for md, read in _indexable(store):
        # as_posix, not str: SlugIndex, _breadcrumb and the wikilink resolver all
        # split a stored path on "/". On Windows str() gives backslashes, so each
        # of those saw one segment — no wikilink edge ever resolved, and the
        # breadcrumb that situates a note for retrieval collapsed to a filename.
        path = md.as_posix()
        if md in seeds and templates.is_unfilled(store.paths, md):
            # An unfilled template says nothing about the project. Checked BEFORE
            # the stat pre-screen, or a seed indexed by an older version would be
            # skipped as unchanged and stay indexed forever. Not `seen`, so that
            # row is swept below; filling it in makes it an ordinary note.
            continue
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
            note = read(md)
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
        if slug_index is None:  # built lazily: an unchanged corpus never needs it
            slug_index = db.SlugIndex(conn)
        db.replace_edges(conn, path, store.extract_wikilinks(note.body), slug_index)
        # Map notes are excluded: they are rendered *from* the symbol table, so
        # their mentions are that table restated — the single largest source of
        # rows and the one that carries no information. What the feature is for
        # is authored memory: decisions, learnings, handoffs.
        mentions = [] if note.tier is Tier.MAP else store.extract_symbol_mentions(note.body)
        db.replace_note_symbols(conn, path, mentions)
        pending.append((path, f"{breadcrumb}\n{note.body}"))  # breadcrumb also situates the embedding

    if pending and embedder_matches:
        vectors = embedder.embed([body for _, body in pending])
        for (path, _), vec in zip(pending, vectors):
            db.upsert_vector(conn, path, vec)
    elif pending:
        warnings.warn(
            f"embedder is {identity} but the index was built with {stored}; "
            "indexing text only and searching without vectors until they agree "
            "(install the `embeddings` extra, or `torsor clean --deep` to rebuild).",
            stacklevel=2,
        )

    deleted = 0
    for path in list(existing):
        if path not in seen:
            db.delete_note(conn, path)
            deleted += 1

    # Heal wikilink edges whose target was indexed after the linking note
    # (insert-order dependence) or has been deleted since. Only when the note
    # set actually moved: re-resolving every edge on an unchanged corpus was
    # pure cost on every recall, and recall reindexes before it searches.
    if pending or deleted:
        db.reresolve_edges(conn)

    # Notes the stat pre-screen skipped never reached the loop above, so on an
    # index built before mentions existed the table would stay empty forever —
    # the feature would simply return nothing, with no way to tell that from
    # "nothing was recorded about this symbol".
    if db.meta_get(conn, "mentions_format") != str(MENTIONS_FORMAT_VERSION):
        _backfill_mentions(store, conn, skip=[path for path, _ in pending])
        db.meta_set(conn, "mentions_format", str(MENTIONS_FORMAT_VERSION))

    if embedder_matches:
        db.meta_set(conn, "embedder", identity)
    db.meta_set(conn, "indexed_format", str(INDEX_FORMAT_VERSION))
    conn.commit()
    return {"indexed": len(pending), "deleted": deleted, "total": len(seen)}
