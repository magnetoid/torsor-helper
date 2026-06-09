from __future__ import annotations

import ast
import hashlib
from collections import Counter
from pathlib import Path

from torsor_helper.budget import truncate_to_tokens
from torsor_helper.models import Symbol, SymbolEdge

DEFAULT_IGNORE = {
    ".torsor", ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".eggs",
}


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


def _norm_module(module: str) -> str:
    """Normalize a module key to dotted form so a file relpath ("pkg/dates.py")
    and an import target ("pkg.dates") compare equal. Strips a leading source-root
    segment ("src/", "lib/") so a src-layout file ("src/pkg/mod.py") canonicalizes
    to its import name ("pkg.mod") and cross-module edges resolve correctly."""
    if module.endswith(".py"):
        module = module[:-3]
    dotted = module.replace("/", ".")
    for root in ("src.", "lib."):
        if dotted.startswith(root):
            return dotted[len(root):]
    return dotted


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """Map each imported name to the module it resolves to (best-effort).

    `from pkg.dates import format_date` → {format_date: "pkg.dates"} (the module
    we imported FROM — always real). `import pkg.dates as d` → {d: "pkg.dates"}.
    """
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for a in node.names:
                aliases[a.asname or a.name] = base
    return aliases


def _owners(tree: ast.Module):
    """Yield (owner_symbol, root_node) pairs covering the whole module body, so
    every reference can be attributed to the top-level symbol that contains it."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
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
    aliases = _import_aliases(tree)

    def resolve(name: str) -> str | None:
        if name in top_defs:
            return module
        return aliases.get(name)

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


def iter_source_files(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> list[Path]:
    root = Path(root)
    out: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in ignore for part in rel_parts):
            continue
        out.append(path)
    return out


def repo_fingerprint(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> str:
    """A cheap O(stat) digest of the repo's *.py files (relpath, mtime, size).

    Lets map_repo skip the whole scan+render+reindex when nothing changed. We
    fingerprint the WHOLE set (all-or-nothing) because refs are cross-file —
    per-file incrementalism would serve silently-stale ref counts."""
    root = Path(root)
    lines: list[str] = []
    for path in iter_source_files(root, ignore):
        try:
            st = path.stat()
        except OSError:
            continue
        lines.append(f"{path.relative_to(root).as_posix()}:{st.st_mtime_ns}:{st.st_size}")
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def _scan(root: Path, paths: list[str] | None, ignore: set[str]) -> tuple[list[Symbol], list[SymbolEdge]]:
    root = Path(root)
    if paths is not None:
        files = [(root / p) if not Path(p).is_absolute() else Path(p) for p in paths]
    else:
        files = iter_source_files(root, ignore)

    symbols: list[Symbol] = []
    edges: list[SymbolEdge] = []
    for file in files:
        file = Path(file)
        try:
            src = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            module = file.relative_to(root).as_posix()
        except ValueError:
            module = file.name
        symbols.extend(extract_symbols(src, module))
        edges.extend(extract_edges(src, module))

    # refs = count of *resolved* references (intra- and cross-module), keyed by
    # (normalized target module, referenced name). Honest — never counts comments
    # or strings, unlike the old substring heuristic.
    counts: Counter[tuple[str, str]] = Counter(
        (_norm_module(e.resolved_module), e.referenced_name) for e in edges if e.resolved_module
    )
    for sym in symbols:
        base = sym.name.split(".")[-1]
        sym.refs = counts.get((_norm_module(sym.module), base), 0)
    return symbols, edges


def scan_repo(root: Path, paths: list[str] | None = None, ignore: set[str] = DEFAULT_IGNORE) -> list[Symbol]:
    return _scan(root, paths, ignore)[0]


def scan_repo_with_edges(
    root: Path, paths: list[str] | None = None, ignore: set[str] = DEFAULT_IGNORE
) -> tuple[list[Symbol], list[SymbolEdge]]:
    return _scan(root, paths, ignore)


def render_map(symbols: list[Symbol], *, overview_tokens: int = 2000, chars_per_token: int = 4) -> dict[str, tuple[str, str]]:
    by_module: dict[str, list[Symbol]] = {}
    for sym in symbols:
        by_module.setdefault(sym.module, []).append(sym)

    out: dict[str, tuple[str, str]] = {}

    overview_lines = ["Modules and their key symbols (ranked by references).", ""]
    for module in sorted(by_module):
        syms = sorted(by_module[module], key=lambda s: (-s.refs, s.line))
        overview_lines.append(f"- **{module}** — {len(syms)} symbol(s)")
        for sym in syms[:5]:
            overview_lines.append(f"  - `{sym.signature}` ({sym.kind})")
    overview = truncate_to_tokens("\n".join(overview_lines), overview_tokens, chars_per_token)
    out["overview.md"] = ("Repository Map", overview)

    for module in sorted(by_module):
        syms = sorted(by_module[module], key=lambda s: s.line)
        lines = [f"Symbols in `{module}`.", ""]
        for sym in syms:
            doc = f" — {sym.doc}" if sym.doc else ""
            lines.append(f"- L{sym.line} `{sym.signature}` ({sym.kind}){doc}")
        safe = module.replace("/", "__")
        out[f"modules/{safe}.md"] = (module, "\n".join(lines))

    return out
