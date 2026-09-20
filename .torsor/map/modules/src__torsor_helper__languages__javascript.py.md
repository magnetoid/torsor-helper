---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/languages/javascript.py

Symbols in `src/torsor_helper/languages/javascript.py`.

- L21 `complexity(text: str, module: str='')` (function) — File-grained complexity proxy (ADR-consistent with python.py's): newline
- L32 `grammar_for(module: str)` (function)
- L41 `_defs_query(grammar: str)` (function)
- L61 `_field_query(grammar: str)` (function)
- L68 `_class_name(node)` (function)
- L73 `_params(fn_node)` (function)
- L78 `_is_top_level(node)` (function) — True when `node` sits directly in `program`, or in an `export_statement`
- L90 `_is_class_member(node)` (function) — True when `node` is a direct child of a class body — excludes a
- L96 `_method_symbol(node, name: str, fn_node, module: str)` (function)
- L104 `extract_symbols(source: str, module: str)` (function)
- L153 `_doc_anchor(node)` (function) — `export function f` wraps the declaration in an export_statement, and the
- L168 `imports(source: str, module: str='')` (function) — Every import/require specifier with its line, for guard/deps. Parses with
- L192 `_refs_query(grammar: str)` (function)
- L205 `_top_level_def_names(grammar: str, root)` (function) — Same-file top-level definition names — the ADR 0004 "own module" case.
- L225 `resolve_relative(specifier: str, module: str)` (function) — `'./x'` / `'../x'` relative to the importing file → module key (suffix
- L238 `_aliases(grammar: str, root, module: str)` (function)
- L251 `_field_name_node(node)` (function) — The name node of a class-field definition — TS/TSX name the field `name`,
- L257 `_owner(node)` (function) — The enclosing symbol a reference is attributed to. Walks up from `node`
- L293 `extract_edges(source: str, module: str)` (function)
- L320 `extract(source: str, module: str)` (function)
