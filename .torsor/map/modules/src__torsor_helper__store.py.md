---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:54'
updated: '2026-09-21T01:02:54'
rules: []
---

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L33 `ensure_ignored(paths)` (function) — Add any missing entry to .torsor/.gitignore, in place. Projects
- L48 `state_file(paths, name: str)` (function) — Path to a non-derivable state file under .torsor/state/, migrating one
- L70 `Store` (class)
- L71 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now)` (method)
- L81 `parse_frontmatter(text: str)` (method)
- L112 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L118 `extract_wikilinks(text: str)` (method) — Link *targets*, in order, deduplicated.
- L137 `content_hash(text: str)` (method)
- L141 `tier_for_path(paths: TorsorPaths, path: Path)` (method) — Which stability tier a note file belongs to, by position.
- L159 `scaffold(self, force: bool=False)` (method)
- L182 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L196 `read_note(self, path: Path)` (method)
- L214 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the derived directories), in
- L236 `iter_notes(self)` (method)
- L245 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L271 `_match_tier(p: Path, anchors: tuple[Path, ...])` (function)
- L280 `_tier_anchors(paths: TorsorPaths)` (function) — ((charter, architecture, map, active) as written, and resolved).
- L296 `_within(path: Path, parent: Path)` (function)
- L301 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
