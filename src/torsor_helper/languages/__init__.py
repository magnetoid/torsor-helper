from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Callable

from torsor_helper.languages import go as _go
from torsor_helper.languages import javascript as _js
from torsor_helper.languages import python as _py
from torsor_helper.models import Symbol, SymbolEdge

Extractor = Callable[[str, str], tuple[list[Symbol], list[SymbolEdge]]]
Resolver = Callable[[list[Symbol], list[SymbolEdge]], None]


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    extractor: Extractor
    requires: tuple[str, ...] = ()               # importable modules the extractor needs
    cross_file_resolver: Resolver | None = None  # run inside compute_refs over the whole graph
    complexity: Callable[[str], int] | None = None
    imports: Callable[[str], list[tuple[str, int]]] | None = None  # (specifier, line) for guard/deps


LANGUAGES: dict[str, LanguageSpec] = {
    "python": LanguageSpec("python", (".py",), _py.extract, complexity=_py.complexity),
    "javascript": LanguageSpec("javascript", (".js", ".jsx", ".mjs", ".cjs"), _js.extract,
                               requires=("tree_sitter", "tree_sitter_javascript")),
    "typescript": LanguageSpec("typescript", (".ts", ".tsx"), _js.extract,
                               requires=("tree_sitter", "tree_sitter_typescript")),
    "go": LanguageSpec("go", (".go",), _go.extract, requires=("tree_sitter", "tree_sitter_go"),
                       cross_file_resolver=_go.resolve_cross_file, imports=_go.imports),
}


@lru_cache(maxsize=None)
def is_available(name: str) -> bool:
    """True when every module the language's extractor needs imports cleanly.
    Python always; the tree-sitter languages only with the [languages] extra."""
    for mod in LANGUAGES[name].requires:
        try:
            import_module(mod)
        except ImportError:
            return False
    return True


def available() -> dict[str, bool]:
    return {name: is_available(name) for name in LANGUAGES}


def source_extensions() -> tuple[str, ...]:
    out: list[str] = []
    for spec in LANGUAGES.values():
        if is_available(spec.name):
            out.extend(spec.extensions)
    return tuple(out)


def spec_for(path) -> LanguageSpec | None:
    suffix = Path(path).suffix
    for spec in LANGUAGES.values():
        if suffix in spec.extensions and is_available(spec.name):
            return spec
    return None


def extractor_for(path) -> Extractor | None:
    spec = spec_for(path)
    return spec.extractor if spec else None


def complexity(path: Path) -> int:
    """File-grained complexity proxy for any registered language; 0 when the
    file is unreadable or its language isn't available."""
    spec = spec_for(path)
    if spec is None or spec.complexity is None:
        return 0
    try:
        return spec.complexity(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return 0


def import_specifiers(relpath: str, text: str) -> list[tuple[str, int]]:
    """(import specifier, line) pairs for a non-Python file; [] when unknown."""
    spec = spec_for(relpath)
    if spec is None or spec.imports is None:
        return []
    return spec.imports(text)
