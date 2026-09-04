from __future__ import annotations

import ast

from torsor_helper.languages.modules import norm_module
from torsor_helper.models import Symbol, SymbolEdge


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return f"{fn.name}({ast.unparse(fn.args)})"
    except Exception:
        return f"{fn.name}(...)"


def _first_line(text: str | None) -> str:
    return (text or "").strip().split("\n", 1)[0]


def extract_symbols(source: str, module: str) -> list[Symbol]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(
                name=node.name, kind="function", signature=_signature(node),
                module=module, line=node.lineno, doc=_first_line(ast.get_docstring(node)),
            ))
        elif isinstance(node, ast.ClassDef):
            out.append(Symbol(
                name=node.name, kind="class", signature=node.name,
                module=module, line=node.lineno, doc=_first_line(ast.get_docstring(node)),
            ))
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(Symbol(
                        name=f"{node.name}.{member.name}", kind="method",
                        signature=_signature(member), module=module, line=member.lineno,
                        doc=_first_line(ast.get_docstring(member)),
                    ))
    return out


def absolute_from_module(node: ast.ImportFrom, module: str) -> str:
    """Resolve an ImportFrom's base module to absolute dotted form, using the
    importing module's path (relpath or dotted) to resolve relative imports.
    `from . import x` / `from .sub import x` in "pkg/mod.py" resolve against
    "pkg"; absolute imports pass through unchanged."""
    base = node.module or ""
    if not node.level:
        return base
    parts = norm_module(module).split(".")[:-1]  # the file's package ("__init__" is a module name too)
    climb = node.level - 1
    if climb > len(parts):
        return base  # climbs past the repo root — leave as written
    if climb:
        parts = parts[: len(parts) - climb]
    prefix = ".".join(parts)
    if base and prefix:
        return f"{prefix}.{base}"
    return base or prefix


def _import_aliases(tree: ast.Module, module: str) -> dict[str, str]:
    """Map each imported name to the module it resolves to (best-effort).

    `from pkg.dates import format_date` → {format_date: "pkg.dates"} (the module
    we imported FROM — always real). `import pkg.dates as d` → {d: "pkg.dates"},
    but a no-asname `import pkg.dates` binds only the top name: {pkg: "pkg"}.
    Relative imports resolve against `module`'s package.
    """
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    aliases[a.asname] = a.name
                else:
                    top = a.name.split(".")[0]
                    aliases[top] = top
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from_module(node, module)
            for a in node.names:
                if base:
                    aliases[a.asname or a.name] = base
    return aliases


def _owners(tree: ast.Module):
    """Yield (owner_symbol, root_node) pairs covering the whole module body, so
    every reference can be attributed to the top-level symbol that contains it."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            # bases, decorators and class keywords (metaclass=...) live on the
            # ClassDef itself, not in its body — without these, `class Foo(Base)`
            # records no edge for Base and impact() misses every subclass.
            for expr in (*node.decorator_list, *node.bases, *node.keywords):
                yield node.name, expr
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{member.name}", member
                else:
                    yield node.name, member
        else:
            yield "<module>", node


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    """Extract resolved reference edges from a module via AST (no substring
    counting). Resolves only the two cheap, reliable cases — same-module
    top-level defs and `from x import y` aliases — and leaves everything else
    unresolved (resolved_module=None), degrading gracefully."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    top_defs = {
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    aliases = _import_aliases(tree, module)

    def resolve(name: str) -> str | None:
        # Always return the canonical dotted form — consumers (who_references,
        # module_edges) must never see a mix of relpaths and dotted names.
        if name in top_defs:
            return norm_module(module)
        target = aliases.get(name)
        return norm_module(target) if target else None

    edges: list[SymbolEdge] = []

    def collect(node: ast.AST, owner: str) -> None:
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                edges.append(SymbolEdge(caller=owner, referenced_name=func.id, role="call",
                                        module=module, resolved_module=resolve(func.id)))
                # don't also record func.id as a read (avoid double counting)
            elif isinstance(func, ast.Attribute):
                receiver = func.value
                resolved = aliases.get(receiver.id) if isinstance(receiver, ast.Name) else None
                edges.append(SymbolEdge(caller=owner, referenced_name=func.attr, role="call",
                                        module=module, resolved_module=resolved))
                collect(func.value, owner)  # the receiver itself is a read
            else:
                collect(func, owner)
            for arg in node.args:
                collect(arg, owner)
            for kw in node.keywords:
                collect(kw.value, owner)
            return
        if isinstance(node, ast.Name):
            role = "write" if isinstance(node.ctx, ast.Store) else "read"
            edges.append(SymbolEdge(caller=owner, referenced_name=node.id, role=role,
                                    module=module, resolved_module=resolve(node.id)))
            return
        for child in ast.iter_child_nodes(node):
            collect(child, owner)

    for owner, root in _owners(tree):
        collect(root, owner)
    return edges


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)


# Branch-y nodes used as a cheap complexity proxy (file-grained; pairs with git
# churn in the Coach). Moved from coach/hotspots so every language has one.
_DECISION_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp)


def complexity(text: str, module: str = "") -> int:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0
    return text.count("\n") + 1 + sum(isinstance(n, _DECISION_NODES) for n in ast.walk(tree))
