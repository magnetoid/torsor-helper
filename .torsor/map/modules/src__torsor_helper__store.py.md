---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L27 `ensure_ignored(paths)` (function) — Add any missing entry to .torsor/.gitignore, in place. Projects
- L42 `state_file(paths, name: str)` (function) — Path to a non-derivable state file under .torsor/state/, migrating one
- L64 `Store` (class)
- L65 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now)` (method)
- L75 `parse_frontmatter(text: str)` (method)
- L100 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L106 `extract_wikilinks(text: str)` (method)
- L115 `content_hash(text: str)` (method)
- L119 `tier_for_path(paths: TorsorPaths, path: Path)` (method)
- L132 `scaffold(self, force: bool=False)` (method)
- L155 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L169 `read_note(self, path: Path)` (method)
- L183 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the disposable index), in
- L194 `iter_notes(self)` (method)
- L203 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L226 `_within(path: Path, parent: Path)` (function)
- L231 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
