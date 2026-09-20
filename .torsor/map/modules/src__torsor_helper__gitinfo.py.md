---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/gitinfo.py

Symbols in `src/torsor_helper/gitinfo.py`.

- L23 `_run(root, *args)` (function)
- L33 `output(root, *args)` (function) — Stdout of a git command, stripped. Empty string on any failure.
- L39 `_zlines(root, *args)` (function)
- L46 `is_repo(root)` (function)
- L50 `toplevel(root)` (function)
- L54 `head(root)` (function)
- L58 `source_extensions()` (function) — Extensions the default change discovery feeds to guard/deps. Derived from
- L67 `rel_to_root(root, top, files)` (function) — Re-anchor git toplevel-relative paths to the torsor root, keeping only
- L84 `changed_source_files(root)` (function) — Source files differing from HEAD in the working tree, plus untracked ones.
- L96 `commit_source_files(root, ref: str='HEAD')` (function) — Source files touched by a single commit — what the post-commit hook
