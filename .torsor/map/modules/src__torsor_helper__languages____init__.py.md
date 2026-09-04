---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T15:38:11'
updated: '2026-09-04T15:38:11'
---

# src/torsor_helper/languages/__init__.py

Symbols in `src/torsor_helper/languages/__init__.py`.

- L19 `LanguageSpec` (class)
- L44 `is_available(name: str)` (function) — True when every module the language's extractor needs imports cleanly.
- L55 `available()` (function)
- L59 `all_extensions()` (function) — Every registered extension, whether or not the language is available —
- L69 `source_extensions()` (function)
- L77 `spec_for(path)` (function)
- L85 `extractor_for(path)` (function)
- L90 `complexity(path: Path)` (function) — File-grained complexity proxy for any registered language; 0 when the
- L104 `import_specifiers(relpath: str, text: str)` (function) — (import specifier, line) pairs for a non-Python file; [] when unknown.
