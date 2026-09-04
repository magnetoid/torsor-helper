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


_OWNER_TYPES = ("function_declaration", "method_definition", "variable_declarator", "class_declaration")


def _class_name(node) -> str:
    name = node.child_by_field_name("name")
    return ts.text(name) if name is not None else ""


def _params(fn_node) -> str:
    params = fn_node.child_by_field_name("parameters") if fn_node is not None else None
    return ts.text(params) if params is not None else "()"


def extract_symbols(source: str, module: str) -> list[Symbol]:
    grammar = grammar_for(module)
    root = ts.parse(grammar, source).root_node
    out: list[Symbol] = []
    for m in ts.matches(grammar, root, _defs_query(grammar)):
        if "function" in m:
            node, name = m["function"][0], ts.text(m["function.name"][0])
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(node)}",
                              module=module, line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "arrow" in m:
            decl, name, fn = m["arrow"][0], ts.text(m["arrow.name"][0]), m["arrow.fn"][0]
            anchor = decl.parent  # the lexical_declaration (or export_statement above it)
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(fn)}",
                              module=module, line=ts.line(decl), doc=ts.leading_comment(_doc_anchor(anchor))))
        elif "class" in m:
            node, name = m["class"][0], ts.text(m["class.name"][0])
            out.append(Symbol(name=name, kind="class", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "method" in m:
            node, name = m["method"][0], ts.text(m["method.name"][0])
            owner = ts.enclosing(node, ("class_declaration", "class"))
            cls = _class_name(owner) if owner is not None else ""
            full = f"{cls}.{name}" if cls else name
            out.append(Symbol(name=full, kind="method", signature=f"{name}{_params(node)}", module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
        elif "type" in m:
            node, name = m["type"][0], ts.text(m["type.name"][0])
            out.append(Symbol(name=name, kind="type", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
    return sorted(out, key=lambda s: s.line)


def _doc_anchor(node):
    """`export function f` wraps the declaration in an export_statement, and the
    JSDoc sits before the *export* — so look for the comment there."""
    return node.parent if node.parent is not None and node.parent.type == "export_statement" else node


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    return []  # Task 3


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)
