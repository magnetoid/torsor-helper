"""The one module that touches tree_sitter (ADR 0013): grammar loading, parsing
and query helpers shared by every tree-sitter language. Imports are lazy so the
package imports cleanly without the [languages] extra."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=None)
def grammar(name: str):
    from tree_sitter import Language

    if name == "javascript":
        import tree_sitter_javascript as m
        return Language(m.language())
    if name == "typescript":
        import tree_sitter_typescript as m
        return Language(m.language_typescript())
    if name == "tsx":
        import tree_sitter_typescript as m
        return Language(m.language_tsx())
    if name == "go":
        import tree_sitter_go as m
        return Language(m.language())
    raise KeyError(name)


@lru_cache(maxsize=None)
def _parser(name: str):
    from tree_sitter import Parser

    return Parser(grammar(name))


@lru_cache(maxsize=None)
def _query(name: str, source: str):
    from tree_sitter import Query

    return Query(grammar(name), source)


def parse(name: str, text: str):
    return _parser(name).parse(text.encode("utf-8"))


def captures(name: str, node, query: str) -> dict[str, list]:
    from tree_sitter import QueryCursor

    return QueryCursor(_query(name, query)).captures(node)


def branch_count(name: str, text: str, query: str) -> int:
    """Number of `@b` captures a branch-node query matches over `text` — the
    shared building block for each language's file-grained complexity proxy."""
    root = parse(name, text).root_node
    return len(captures(name, root, query).get("b", []))


def matches(name: str, node, query: str) -> list[dict[str, list]]:
    from tree_sitter import QueryCursor

    return [caps for _pattern, caps in QueryCursor(_query(name, query)).matches(node)]


def text(node) -> str:
    return node.text.decode("utf-8", errors="replace")


def line(node) -> int:
    return node.start_point[0] + 1


def leading_comment(node) -> str:
    """First line of the comment immediately preceding `node` (JSDoc, `//`, `#`),
    stripped of comment syntax — the cross-language analogue of a docstring."""
    prev = node.prev_named_sibling
    if prev is None or prev.type != "comment":
        return ""
    raw = text(prev).strip()
    for lead in ("/**", "/*", "//", "#"):
        if raw.startswith(lead):
            raw = raw[len(lead):]
            break
    first = raw.strip().split("\n", 1)[0].strip()
    return first.lstrip("* ").rstrip("*/ ").strip()


def enclosing(node, types: tuple[str, ...]):
    """Nearest ancestor whose type is in `types`, or None."""
    cur = node.parent
    while cur is not None:
        if cur.type in types:
            return cur
        cur = cur.parent
    return None
