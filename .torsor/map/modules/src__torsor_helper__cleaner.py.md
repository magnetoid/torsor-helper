---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:01'
updated: '2026-09-04T05:04:01'
---

# src/torsor_helper/cleaner.py

Symbols in `src/torsor_helper/cleaner.py`.

- L12 `CleanPlan` (class) — What a clean pass *would* reclaim. Building one never touches disk.
- L22 `files(self)` (method)
- L26 `reclaimed_bytes(self)` (method) — Bytes the listed files occupy. Dead index rows are excluded — what
- L32 `is_empty(self)` (method)
- L36 `_size(path: Path)` (function)
- L45 `_map_note_name(module: str)` (function) — The map-note filename cartographer.render_map writes for `module` —
- L52 `_live_map_notes(store)` (function) — Map-note filenames for indexed modules whose source file still exists.
- L62 `_plan_map_orphans(store, out: CleanPlan)` (function)
- L84 `_dead_rows(store, conn)` (function)
- L97 `_plan_journal_expiry(store, config, out: CleanPlan)` (function)
- L116 `plan(store, config, *, deep: bool=False)` (function) — Compute what a clean pass would reclaim. Strictly read-only: this is the
- L136 `_purge_dead_rows(store, conn)` (function)
- L148 `apply(store, config, plan: CleanPlan)` (function) — Execute `plan`. Only ever removes derived or expired artefacts — never a
- L188 `_vacuum(conn, db_path: Path)` (function) — VACUUM the index and report the bytes it actually gave back.
