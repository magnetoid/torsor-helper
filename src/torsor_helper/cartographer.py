from __future__ import annotations

import hashlib
import os
from collections import Counter
from pathlib import Path

from torsor_helper import languages
from torsor_helper.budget import truncate_to_tokens
# norm_module is re-exported deliberately: operations, export, hubs and
# coupling all reach it through cartographer, and the two functions must be
# picked apart by the caller (see languages/modules.py).
from torsor_helper.languages.modules import norm_module, norm_path  # noqa: F401
from torsor_helper.languages.python import absolute_from_module, extract_edges, extract_symbols  # noqa: F401  (back-compat re-exports)
from torsor_helper.models import Symbol, SymbolEdge
from torsor_helper.paths import contained


DEFAULT_IGNORE = {
    ".torsor", ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".eggs",
    ".next", ".turbo", "coverage", "vendor", "target", ".claude",
}


def iter_files(root: Path, ignore: set[str] = DEFAULT_IGNORE, *, skip_hidden: bool = False) -> list[Path]:
    """Every file under `root` not inside an ignored directory, sorted by path.
    With skip_hidden, dot-directories are skipped too (the Coach/practices walks
    want that; the map does not — `.github/scripts/x.py` is real code).

    Prunes DURING traversal: `os.walk` with `dirnames` filtered in place never
    descends into `node_modules`/`.git`/`.venv` at all. The previous
    `rglob("*")` materialized and stat'd every file under those trees before
    filtering them out — 2.4x-27x slower on repos with big vendored trees.
    Symlinked directories are not followed (os.walk's default), so a symlink
    cycle can't hang the walk."""
    root = Path(root)
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in ignore and not (skip_hidden and d.startswith("."))
        )
        here = Path(dirpath)
        for name in sorted(filenames):
            path = here / name
            if path.is_file():  # excludes broken symlinks and fifos, as rglob's is_file() did
                out.append(path)
    return sorted(out)  # os.walk is depth-first per level; callers rely on whole-tree path order


def iter_source_files(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> list[Path]:
    exts = set(languages.source_extensions())
    return [p for p in iter_files(root, ignore) if p.suffix in exts]


# Part of the fingerprint, so a change to WHAT the map stores forces one full
# remap. Without it, an index built by an older version is skipped forever as
# "unchanged" — its fingerprint still matches the files — and keeps whatever
# the old version wrote. 2: unresolvable non-Go edges are no longer stored.
MAP_FORMAT = 2


def repo_fingerprint(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> str:
    """A cheap O(stat) digest of the repo's source files (relpath, mtime, size).

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
    return f"{MAP_FORMAT}:" + hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def _scan(root: Path, paths: list[str] | None, ignore: set[str]) -> tuple[list[Symbol], list[SymbolEdge]]:
    root = Path(root)
    if paths is not None:
        # An explicit path list reaches here from map_repo (an MCP tool) and the
        # post-commit hook; anything outside the repo is not ours to parse.
        files = [f for f in (contained(root, p) for p in paths) if f is not None]
    else:
        files = iter_source_files(root, ignore)

    symbols: list[Symbol] = []
    edges: list[SymbolEdge] = []
    for file in files:
        file = Path(file)
        try:
            # utf-8-sig: a BOM (common from Windows editors) is a SyntaxError to
            # ast.parse and would silently drop the file from the map.
            src = file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            module = file.relative_to(root).as_posix()
        except ValueError:
            module = file.name
        extractor = languages.extractor_for(file)
        if extractor is None:
            continue
        syms, eds = extractor(src, module)
        symbols.extend(syms)
        edges.extend(eds)

    compute_refs(symbols, edges)
    return symbols, edges


def compute_refs(symbols: list[Symbol], edges: list[SymbolEdge]) -> None:
    """Set each symbol's `refs` in place from the given edge set. refs = count of
    *resolved* references (intra- and cross-module), keyed by (normalized target
    module, referenced name). Honest — never counts comments or strings, unlike
    the old substring heuristic. Reused when merging a partial map into the full
    graph, so the whole (symbols, edges) union must be passed for counts to be
    correct — a subset would undercount cross-module references."""
    for spec in languages.LANGUAGES.values():
        if spec.cross_file_resolver is not None and languages.is_available(spec.name):
            spec.cross_file_resolver(symbols, edges)
    # e.resolved_module is already the canonical dotted key (see SymbolEdge) —
    # never re-normalize it, only sym.module (a file path).
    counts: Counter[tuple[str, str]] = Counter(
        (e.resolved_module, e.referenced_name) for e in edges if e.resolved_module
    )
    for sym in symbols:
        if "." in sym.name:
            sym.refs = 0  # methods score 0 by design (ADR 0004) — resolution only targets top-level names
            continue
        sym.refs = counts.get((norm_path(sym.module), sym.name), 0)


def persistable_edges(edges: list[SymbolEdge]) -> list[SymbolEdge]:
    """The edges worth writing to the index: resolved ones, plus every edge of a
    language that has a cross-file resolver.

    On a real 3 200-file project the rest were 845 962 of 1 071 508 rows —
    references to `self`, `str`, `result`, `len` — and 79% of a 172 MB table
    and its indexes. Python and JS resolve an edge while extracting it and have
    no cross-file resolver, so an edge unresolved then stays unresolved forever;
    and every query that reads edges filters on `resolved_module IS NOT NULL`.
    Go's resolver re-resolves every Go edge over the merged graph (a bare call
    resolves once a sibling file gains the symbol), so Go keeps all of them.

    Dropping them keeps ADR 0008's invariant: compute_refs counts resolved edges
    only and runs resolvers only over languages that have one, so a partial
    merge reloading this subset reaches the same state as a full remap."""
    keep_unresolved: dict[str, bool] = {}
    out: list[SymbolEdge] = []
    for e in edges:
        if e.resolved_module:
            out.append(e)
            continue
        suffix = Path(e.module).suffix
        if suffix not in keep_unresolved:
            spec = languages.spec_for(Path(e.module))
            keep_unresolved[suffix] = spec is not None and spec.cross_file_resolver is not None
        if keep_unresolved[suffix]:
            out.append(e)
    return out


def scanned_modules(root: Path, paths: list[str]) -> set[str]:
    """The module keys a partial scan of `paths` covers — mirrors how `_scan`
    derives a file's module, so callers can scope a merge to exactly the files
    that were rescanned (including ones that now yield zero symbols)."""
    root = Path(root)
    mods: set[str] = set()
    for p in paths:
        fp = (root / p) if not Path(p).is_absolute() else Path(p)
        try:
            mods.add(fp.relative_to(root).as_posix())
        except ValueError:
            mods.add(fp.name)
    return mods


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
