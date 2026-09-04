"""Go: symbols, edges, and the two reliable resolutions (ADR 0004) — same file,
and same *package* (Go's normal case: a call to a function defined in another
file of the same directory), plus `pkg.Fn` where the import path's tail names a
directory in this repo. Stdlib and third-party imports stay unresolved."""
from __future__ import annotations

import posixpath

from torsor_helper.languages import treesitter as ts
from torsor_helper.languages.modules import norm_module
from torsor_helper.models import Symbol, SymbolEdge

_DEFS = """
(function_declaration name: (identifier) @function.name) @function
(method_declaration receiver: (parameter_list (parameter_declaration
    type: [(pointer_type (type_identifier) @method.recv) (type_identifier) @method.recv]))
  name: (field_identifier) @method.name) @method
(type_declaration (type_spec name: (type_identifier) @type.name)) @type
"""
_REFS = """
(call_expression function: (identifier) @call)
(call_expression function: (selector_expression operand: (identifier) @pkg field: (field_identifier) @qualified))
(composite_literal type: (type_identifier) @call)
"""
_IMPORTS = "(import_spec path: (interpreted_string_literal) @path)"


def _params(node) -> str:
    p = node.child_by_field_name("parameters")
    return ts.text(p) if p is not None else "()"


def extract_symbols(source: str, module: str) -> list[Symbol]:
    root = ts.parse("go", source).root_node
    out: list[Symbol] = []
    for m in ts.matches("go", root, _DEFS):
        if "function" in m:
            node, name = m["function"][0], ts.text(m["function.name"][0])
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(node)}", module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
        elif "method" in m:
            node, name, recv = m["method"][0], ts.text(m["method.name"][0]), ts.text(m["method.recv"][0])
            out.append(Symbol(name=f"{recv}.{name}", kind="method", signature=f"{name}{_params(node)}",
                              module=module, line=ts.line(node), doc=ts.leading_comment(node)))
        elif "type" in m:
            node, name = m["type"][0], ts.text(m["type.name"][0])
            out.append(Symbol(name=name, kind="type", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
    return sorted(out, key=lambda s: s.line)


def imports(source: str) -> list[tuple[str, int]]:
    root = ts.parse("go", source).root_node
    return [(ts.text(n).strip('"'), ts.line(n)) for n in ts.captures("go", root, _IMPORTS).get("path", [])]


def _owner(node) -> str:
    fn = ts.enclosing(node, ("function_declaration", "method_declaration"))
    if fn is None:
        return "<module>"
    name = ts.text(fn.child_by_field_name("name"))
    if fn.type == "method_declaration":
        recv = fn.child_by_field_name("receiver")
        tid = next((n for n in _walk(recv) if n.type == "type_identifier"), None)
        return f"{ts.text(tid)}.{name}" if tid is not None else name
    return name


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    root = ts.parse("go", source).root_node
    own = norm_module(module)
    top = {s.name for s in extract_symbols(source, module) if "." not in s.name}
    # package alias → import path ("util" → "example.com/app/util"); explicit aliases too
    paths: dict[str, str] = {}
    for spec, _line in imports(source):
        paths[spec.rsplit("/", 1)[-1]] = spec
    for n in ts.captures("go", root, "(import_spec name: (package_identifier) @alias path: (interpreted_string_literal) @p)").get("alias", []):
        paths[ts.text(n)] = ts.text(n.next_named_sibling).strip('"')

    edges: list[SymbolEdge] = []
    caps = ts.captures("go", root, _REFS)
    for node in caps.get("call", []):
        name = ts.text(node)
        edges.append(SymbolEdge(caller=_owner(node), referenced_name=name, role="call", module=module,
                                resolved_module=own if name in top else None))
    for pkg, member in zip(caps.get("pkg", []), caps.get("qualified", [])):
        edges.append(SymbolEdge(caller=_owner(member), referenced_name=ts.text(member), role="call",
                                module=module, resolved_module=None, hint=paths.get(ts.text(pkg))))
    return edges


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)


def resolve_cross_file(symbols: list[Symbol], edges: list[SymbolEdge]) -> None:
    """Fill `resolved_module` for Go edges the single-file pass couldn't: a bare
    call to a top-level symbol in another file of the same directory, or
    `pkg.Fn` whose import path ends with a directory that exists in the scanned
    repo. Idempotent — only touches edges still unresolved. `resolved_module` is
    always the canonical dotted key (norm_module of the target file), matching
    what `extract_edges`'s same-file case already stores."""
    by_dir: dict[str, dict[str, str]] = {}
    for s in symbols:
        if s.module.endswith(".go") and "." not in s.name:
            by_dir.setdefault(posixpath.dirname(s.module), {})[s.name] = s.module
    dirs = sorted(by_dir, key=len, reverse=True)  # longest suffix wins
    for e in edges:
        if not e.module.endswith(".go") or e.resolved_module is not None:
            continue
        if e.hint:
            target_dir = next((d for d in dirs if d and (e.hint == d or e.hint.endswith("/" + d))), None)
            if target_dir is not None:
                target = by_dir[target_dir].get(e.referenced_name)
                if target is not None:
                    e.resolved_module = norm_module(target)
            continue
        target = by_dir.get(posixpath.dirname(e.module), {}).get(e.referenced_name)
        if target is not None:
            e.resolved_module = norm_module(target)


_BRANCHES = """
[(if_statement) (for_statement) (expression_case) (type_case) (communication_case) (select_statement)] @b
(binary_expression operator: ["&&" "||"]) @b
"""


def complexity(text: str) -> int:
    root = ts.parse("go", text).root_node
    return text.count("\n") + 1 + len(ts.captures("go", root, _BRANCHES).get("b", []))
