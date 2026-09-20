---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T00:06:46'
updated: '2026-09-21T00:06:46'
---

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L33 `ensure_ignored(paths)` (function) — Add any missing entry to .torsor/.gitignore, in place. Projects
- L48 `state_file(paths, name: str)` (function) — Path to a non-derivable state file under .torsor/state/, migrating one
- L70 `Store` (class)
- L71 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now)` (method)
- L81 `parse_frontmatter(text: str)` (method)
- L106 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L112 `extract_wikilinks(text: str)` (method)
- L121 `content_hash(text: str)` (method)
- L125 `tier_for_path(paths: TorsorPaths, path: Path)` (method) — Which stability tier a note file belongs to, by position.
- L143 `scaffold(self, force: bool=False)` (method)
- L166 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L180 `read_note(self, path: Path)` (method)
- L194 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the derived directories), in
- L216 `iter_notes(self)` (method)
- L225 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L251 `_match_tier(p: Path, anchors: tuple[Path, ...])` (function)
- L260 `_tier_anchors(paths: TorsorPaths)` (function) — ((charter, architecture, map, active) as written, and resolved).
- L276 `_within(path: Path, parent: Path)` (function)
- L281 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
