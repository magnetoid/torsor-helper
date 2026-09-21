---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:33:16'
updated: '2026-09-21T17:33:16'
rules: []
---

# src/torsor_helper/indexer.py

Symbols in `src/torsor_helper/indexer.py`.

- L27 `_is_fallback(stored: str | None, embedder)` (function) — True when this run is the hashing fallback standing in for the embedder
- L33 `_embedder_identity(embedder)` (function)
- L37 `_breadcrumb(note)` (function) — A structural situating prefix (tier + path tail + title) for retrieval.
- L49 `_backfill_mentions(store: Store, conn, *, skip)` (function) — Fill db.note_symbols for notes this run did not re-read. Reads and parses
- L66 `reindex(store: Store, conn, embedder, *, full: bool=False)` (function)
