from __future__ import annotations

import ast
from pathlib import Path

from torsor_helper.budget import truncate_to_tokens
from torsor_helper.models import Symbol

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


def iter_source_files(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> list[Path]:
    root = Path(root)
    out: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in ignore for part in rel_parts):
            continue
        out.append(path)
    return out


def scan_repo(root: Path, paths: list[str] | None = None, ignore: set[str] = DEFAULT_IGNORE) -> list[Symbol]:
    root = Path(root)
    if paths is not None:
        files = [(root / p) if not Path(p).is_absolute() else Path(p) for p in paths]
    else:
        files = iter_source_files(root, ignore)

    texts: dict[str, str] = {}
    symbols: list[Symbol] = []
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
        texts[module] = src
        symbols.extend(extract_symbols(src, module))

    blob = "\n".join(texts.values())
    for sym in symbols:
        base = sym.name.split(".")[-1]
        sym.refs = max(0, blob.count(base) - 1)  # minus the definition itself
    return symbols


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
