---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L21 `Store` (class)
- L22 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now)` (method)
- L32 `parse_frontmatter(text: str)` (method)
- L57 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L63 `extract_wikilinks(text: str)` (method)
- L72 `content_hash(text: str)` (method)
- L76 `tier_for_path(paths: TorsorPaths, path: Path)` (method)
- L89 `scaffold(self, force: bool=False)` (method)
- L112 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L126 `read_note(self, path: Path)` (method)
- L140 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the disposable index), in
- L151 `iter_notes(self)` (method)
- L160 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L183 `_within(path: Path, parent: Path)` (function)
- L188 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
