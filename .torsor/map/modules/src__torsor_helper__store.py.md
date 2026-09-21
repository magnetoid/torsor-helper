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

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L39 `ensure_ignored(paths)` (function) — Add any missing entry to .torsor/.gitignore, in place. Projects
- L54 `state_file(paths, name: str)` (function) — Path to a non-derivable state file under .torsor/state/, migrating one
- L76 `Store` (class)
- L77 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now, journal_partition: str='date')` (method)
- L94 `parse_frontmatter(text: str)` (method)
- L125 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L131 `extract_wikilinks(text: str)` (method) — Link *targets*, in order, deduplicated.
- L150 `extract_symbol_mentions(text: str)` (method) — Code identifiers a note names in `backticks`, in order, deduplicated.
- L183 `content_hash(text: str)` (method)
- L187 `tier_for_path(paths: TorsorPaths, path: Path)` (method) — Which stability tier a note file belongs to, by position.
- L205 `scaffold(self, force: bool=False)` (method)
- L235 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L249 `read_note(self, path: Path)` (method)
- L267 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the derived directories), in
- L289 `iter_notes(self)` (method)
- L298 `journal_author(self)` (method) — The author slug this Store partitions journals by, cached per Store
- L309 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L344 `_match_tier(p: Path, anchors: tuple[Path, ...])` (function)
- L353 `_tier_anchors(paths: TorsorPaths)` (function) — ((charter, architecture, map, active) as written, and resolved).
- L369 `_within(path: Path, parent: Path)` (function)
- L374 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
