---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# tests/test_coach_staleness.py

Symbols in `tests/test_coach_staleness.py`.

- L14 `_store(tmp_path)` (function)
- L20 `_note(store, name, body)` (function)
- L25 `test_dangling_link_flagged_then_cleared(tmp_path)` (function)
- L37 `test_resolved_wikilink_not_flagged(tmp_path)` (function)
- L44 `test_missing_path_ref_flagged_then_cleared(tmp_path)` (function)
- L56 `test_existing_path_ref_not_flagged(tmp_path)` (function)
- L64 `test_bare_filename_without_slash_is_ignored(tmp_path)` (function)
- L71 `test_urls_and_fenced_code_are_ignored(tmp_path)` (function)
- L77 `test_findings_have_stable_keys(tmp_path)` (function)
- L85 `test_dangling_links_ignores_generated_map_notes(tmp_path)` (function) — A map note is rendered from code, not authored. A `[[...]]` inside a
- L107 `test_dangling_links_still_fires_on_an_authored_note(tmp_path)` (function)
