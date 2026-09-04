"""JavaScript / TypeScript / TSX: symbols, reference edges and relative-import
resolution over the official tree-sitter grammars. Resolves only the two
reliable cases (ADR 0004): same-file top-level definitions and names bound by a
relative `import … from './x'` / `require('./x')`."""
from __future__ import annotations

from torsor_helper.languages import treesitter as ts
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


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    return []  # Task 3


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)
