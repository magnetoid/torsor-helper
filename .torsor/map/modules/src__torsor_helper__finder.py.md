---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/finder.py

Symbols in `src/torsor_helper/finder.py`.

- L14 `_seq_score(query: str, text: str)` (function) — Greedy subsequence score, or None if `query` is not a subsequence of
- L48 `fuzzy_score(query: str, text: str)` (function) — Best fuzzy score across the whole path and its basename (filename matches
- L62 `_literal_score(query: str, text: str)` (function)
- L76 `_regex_score(query: str, text: str)` (function)
- L87 `_score(query: str, text: str, mode: str)` (function)
- L95 `_git_files(root: Path)` (function)
- L108 `_walk_files(root: Path)` (function)
- L120 `list_files(root)` (function) — Repo files (git-tracked + untracked-not-ignored, or an ignore-filtered
- L131 `_frecency_boost(entry, clock: int)` (function)
- L138 `find(store, config, query, *, mode='fuzzy', limit=20, include_files=True, include_symbols=True)` (function) — Fuzzy/literal/regex search over repo files + mapped symbols, ranked by
