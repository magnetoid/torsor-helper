"""JavaScript / TypeScript / TSX: symbols, reference edges and relative-import
resolution over the official tree-sitter grammars. Resolves only the two
reliable cases (ADR 0004): same-file top-level definitions and names bound by a
relative `import … from './x'` / `require('./x')`."""
from __future__ import annotations

import posixpath

from torsor_helper.languages import treesitter as ts
from torsor_helper.languages.modules import norm_module
from torsor_helper.models import Symbol, SymbolEdge


def grammar_for(module: str) -> str:
    if module.endswith(".tsx"):
        return "tsx"
    if module.endswith(".ts"):
        return "typescript"
    return "javascript"


# The class name node differs per grammar; everything else is shared.
def _defs_query(grammar: str) -> str:
    class_name = "(type_identifier)" if grammar in ("typescript", "tsx") else "(identifier)"
    q = f"""
(function_declaration name: (identifier) @function.name) @function
(lexical_declaration (variable_declarator name: (identifier) @arrow.name
                       value: [(arrow_function) (function_expression)] @arrow.fn) @arrow)
(class_declaration name: {class_name} @class.name) @class
(method_definition name: (property_identifier) @method.name) @method
"""
    if grammar in ("typescript", "tsx"):
        q += """
(interface_declaration name: (type_identifier) @type.name) @type
(type_alias_declaration name: (type_identifier) @type.name) @type
"""
    return q


# A class-field arrow/function method: `bar = () => {}` / `bar = function() {}`.
# The field-name node's *field name* differs per grammar — TS/TSX name it
# `name`, JS names it `property` — everything else is shared.
def _field_query(grammar: str) -> str:
    node_type = "public_field_definition" if grammar in ("typescript", "tsx") else "field_definition"
    name_field = "name" if grammar in ("typescript", "tsx") else "property"
    return (f"({node_type} {name_field}: (property_identifier) @field.name "
            f"value: [(arrow_function) (function_expression)] @field.fn) @field")


def _class_name(node) -> str:
    name = node.child_by_field_name("name")
    return ts.text(name) if name is not None else ""


def _params(fn_node) -> str:
    params = fn_node.child_by_field_name("parameters") if fn_node is not None else None
    return ts.text(params) if params is not None else "()"


def _is_top_level(node) -> bool:
    """True when `node` sits directly in `program`, or in an `export_statement`
    that itself sits in `program` — mirrors python.py's extract_symbols, which
    only walks the module's top-level `tree.body` (never a nested scope)."""
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "program":
        return True
    return parent.type == "export_statement" and parent.parent is not None and parent.parent.type == "program"


def _is_class_member(node) -> bool:
    """True when `node` is a direct child of a class body — excludes a
    same-shaped `method_definition` inside an object literal."""
    return node.parent is not None and node.parent.type == "class_body"


def _method_symbol(node, name: str, fn_node, module: str) -> Symbol:
    owner = ts.enclosing(node, ("class_declaration", "class"))
    cls = _class_name(owner) if owner is not None else ""
    full = f"{cls}.{name}" if cls else name
    return Symbol(name=full, kind="method", signature=f"{name}{_params(fn_node)}", module=module,
                  line=ts.line(node), doc=ts.leading_comment(node))


def extract_symbols(source: str, module: str) -> list[Symbol]:
    grammar = grammar_for(module)
    root = ts.parse(grammar, source).root_node
    out: list[Symbol] = []
    for m in ts.matches(grammar, root, _defs_query(grammar)):
        if "function" in m:
            node = m["function"][0]
            if not _is_top_level(node):
                continue
            name = ts.text(m["function.name"][0])
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(node)}",
                              module=module, line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "arrow" in m:
            decl = m["arrow"][0]  # the variable_declarator
            anchor = decl.parent  # the lexical_declaration; _doc_anchor climbs past `export` itself
            if not _is_top_level(anchor):
                continue
            name, fn = ts.text(m["arrow.name"][0]), m["arrow.fn"][0]
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(fn)}",
                              module=module, line=ts.line(decl), doc=ts.leading_comment(_doc_anchor(anchor))))
        elif "class" in m:
            node = m["class"][0]
            if not _is_top_level(node):
                continue
            name = ts.text(m["class.name"][0])
            out.append(Symbol(name=name, kind="class", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "method" in m:
            node = m["method"][0]
            if not _is_class_member(node):
                continue
            name = ts.text(m["method.name"][0])
            out.append(_method_symbol(node, name, node, module))
        elif "type" in m:
            node = m["type"][0]
            if not _is_top_level(node):
                continue
            name = ts.text(m["type.name"][0])
            out.append(Symbol(name=name, kind="type", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
    for m in ts.matches(grammar, root, _field_query(grammar)):
        node = m["field"][0]
        if not _is_class_member(node):
            continue
        name = ts.text(m["field.name"][0])
        out.append(_method_symbol(node, name, m["field.fn"][0], module))
    return sorted(out, key=lambda s: s.line)


def _doc_anchor(node):
    """`export function f` wraps the declaration in an export_statement, and the
    JSDoc sits before the *export* — so look for the comment there."""
    return node.parent if node.parent is not None and node.parent.type == "export_statement" else node


_IMPORTS = """
(import_statement (import_clause (identifier) @name) source: (string) @source)
(import_statement (import_clause (named_imports (import_specifier name: (identifier) @name))) source: (string) @source)
(import_statement (import_clause (namespace_import (identifier) @name)) source: (string) @source)
(variable_declarator name: (identifier) @name
  value: (call_expression function: (identifier) @_req arguments: (arguments (string) @source)))
"""


def _refs_query(grammar: str) -> str:
    # `class X extends Base`: plain JS puts the identifier directly in
    # class_heritage; TS/TSX wrap it in an extends_clause with a `value` field.
    heritage = ("(extends_clause value: (identifier) @read)" if grammar in ("typescript", "tsx")
                else "(class_heritage (identifier) @read)")
    return f"""
(call_expression function: (identifier) @call)
(new_expression constructor: (identifier) @call)
{heritage}
(call_expression function: (member_expression object: (identifier) @receiver property: (property_identifier) @member))
"""


def _top_level_def_names(grammar: str, root) -> set[str]:
    """Same-file top-level definition names — the ADR 0004 "own module" case.
    Reuses `_defs_query` (the same query `extract_symbols` matches against) and
    gates each candidate with the same `_is_top_level` test, so a name that
    merely collides with a *nested* local function/class (never a real symbol)
    is never mistaken for the top-level one (R8)."""
    names: set[str] = set()
    for m in ts.matches(grammar, root, _defs_query(grammar)):
        if "function" in m:
            if _is_top_level(m["function"][0]):
                names.add(ts.text(m["function.name"][0]))
        elif "arrow" in m:
            if _is_top_level(m["arrow"][0].parent):  # the lexical_declaration
                names.add(ts.text(m["arrow.name"][0]))
        elif "class" in m:
            if _is_top_level(m["class"][0]):
                names.add(ts.text(m["class.name"][0]))
    return names


def resolve_relative(specifier: str, module: str) -> str | None:
    """`'./x'` / `'../x'` relative to the importing file → module key (suffix
    stripped, `index` collapsed by norm_module). Bare specifiers and paths that
    climb out of the repo → None (ADR 0004: only the reliable cases)."""
    spec = specifier.strip("'\"`")
    if not spec.startswith("."):
        return None
    rel = posixpath.normpath(posixpath.join(posixpath.dirname(module), spec))
    if rel.startswith(".."):
        return None
    return norm_module(rel)


def _aliases(grammar: str, root, module: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for m in ts.matches(grammar, root, _IMPORTS):
        if "_req" in m and ts.text(m["_req"][0]) != "require":
            continue
        if "name" in m and "source" in m:
            out[ts.text(m["name"][0])] = resolve_relative(ts.text(m["source"][0]), module)
    return out


_FIELD_NODE_TYPES = ("public_field_definition", "field_definition")


def _field_name_node(node):
    """The name node of a class-field definition — TS/TSX name the field `name`,
    plain JS names it `property` (mirrors `_field_query`'s per-grammar field)."""
    return node.child_by_field_name("name") or node.child_by_field_name("property")


def _owner(node) -> str:
    """The enclosing symbol a reference is attributed to. Walks up from `node`
    and stops at the OUTERMOST qualifying container — a top-level function/arrow/
    class, `Class.method` for a direct class-body member, or `Class.field` for a
    class-field arrow/function (`onClick = (e) => {...}`) — never at a nested
    local function, which `_is_top_level`/`_is_class_member` isn't a symbol
    (mirrors python.py's `_owners`: a call inside a nested helper inside `run()`
    is attributed to `run`, not to `helper`)."""
    cur = node.parent
    while cur is not None:
        if cur.type == "function_declaration" and _is_top_level(cur):
            return _class_name(cur)
        if cur.type == "method_definition" and _is_class_member(cur):
            cls = ts.enclosing(cur, ("class_declaration", "class"))
            name = _class_name(cur)
            return f"{_class_name(cls)}.{name}" if cls is not None else name
        if cur.type in _FIELD_NODE_TYPES and _is_class_member(cur):
            value = cur.child_by_field_name("value")
            if value is not None and value.type in ("arrow_function", "function_expression"):
                name_node = _field_name_node(cur)
                if name_node is not None:
                    cls = ts.enclosing(cur, ("class_declaration", "class"))
                    name = ts.text(name_node)
                    return f"{_class_name(cls)}.{name}" if cls is not None else name
        if cur.type == "variable_declarator":
            value = cur.child_by_field_name("value")
            if value is not None and value.type in ("arrow_function", "function_expression"):
                anchor = cur.parent  # lexical_declaration; _doc_anchor climbs past `export` itself
                if _is_top_level(anchor):
                    return _class_name(cur)
        if cur.type == "class_declaration" and _is_top_level(cur):
            return _class_name(cur)
        cur = cur.parent
    return "<module>"


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    grammar = grammar_for(module)
    root = ts.parse(grammar, source).root_node
    own = norm_module(module)
    top_defs = _top_level_def_names(grammar, root)
    aliases = _aliases(grammar, root, module)

    def resolve(name: str) -> str | None:
        if name in top_defs:
            return own
        return aliases.get(name)

    edges: list[SymbolEdge] = []
    caps = ts.captures(grammar, root, _refs_query(grammar))
    for role in ("call", "read"):
        for node in caps.get(role, []):
            name = ts.text(node)
            edges.append(SymbolEdge(caller=_owner(node), referenced_name=name, role=role,
                                    module=module, resolved_module=resolve(name)))
    # `ns.fn()` where `ns` came from `import * as ns from './x'` → edge to fn in x.
    for receiver, member in zip(caps.get("receiver", []), caps.get("member", [])):
        target = aliases.get(ts.text(receiver))
        edges.append(SymbolEdge(caller=_owner(member), referenced_name=ts.text(member), role="call",
                                module=module, resolved_module=target))
    return edges


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)
