---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:30'
updated: '2026-11-02T02:18:30'
rules: []
---

# src/torsor_helper/store.py

Symbols in `src/torsor_helper/store.py`.

- L39 `ensure_ignored(paths)` (function) — Add any missing entry to .torsor/.gitignore, in place. Projects
- L54 `state_file(paths, name: str)` (function) — Path to a non-derivable state file under .torsor/state/, migrating one
- L76 `Store` (class)
- L77 `__init__(self, paths: TorsorPaths, clock: Callable[[], datetime]=datetime.now, journal_partition: str='date', doc_sources: Sequence[str]=())` (method)
- L98 `for_config(cls, paths: TorsorPaths, config, **kwargs)` (method) — The Store an adapter should build: every torsor.toml knob that
- L114 `parse_frontmatter(text: str)` (method)
- L145 `serialize(frontmatter: Frontmatter, title: str, body: str)` (method)
- L151 `extract_wikilinks(text: str)` (method) — Link *targets*, in order, deduplicated.
- L170 `extract_symbol_mentions(text: str)` (method) — Code identifiers a note names in `backticks`, in order, deduplicated.
- L203 `content_hash(text: str)` (method)
- L207 `tier_for_path(paths: TorsorPaths, path: Path)` (method) — Which stability tier a note file belongs to, by position.
- L225 `scaffold(self, force: bool=False)` (method)
- L248 `write_note(self, path: Path, frontmatter: Frontmatter, title: str, body: str)` (method)
- L262 `read_note(self, path: Path)` (method)
- L280 `iter_note_paths(self)` (method) — All note files in the pyramid (excluding the derived directories), in
- L302 `iter_doc_paths(self)` (method) — Project Markdown matched by `doc_sources`, outside .torsor/.
- L318 `read_doc(self, path: Path)` (method) — A project doc as a note: the DOCS tier, and type "doc" unless its
- L328 `iter_docs(self)` (method)
- L335 `iter_notes(self)` (method)
- L344 `journal_author(self)` (method) — The author slug this Store partitions journals by, cached per Store
- L355 `append_journal(self, content: str, kind: str, links: list[str])` (method)
- L390 `_expand_doc_source(root: Path, base: Path, pattern: str)` (function)
- L436 `_match_tier(p: Path, anchors: tuple[Path, ...])` (function)
- L445 `_tier_anchors(paths: TorsorPaths)` (function) — ((charter, architecture, map, active) as written, and resolved).
- L461 `_within(path: Path, parent: Path)` (function)
- L466 `_split_title(body: str, fallback: str)` (function) — Return (title, body-without-leading-H1).
