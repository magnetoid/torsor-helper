"""Path-aware globs: the one translation from a glob to a regex.

A leaf — imports nothing from torsor — so both the guard (rule scopes) and the
store (project-doc sources) can use it without a cycle: the guard already
imports the store.
"""
from __future__ import annotations

import re

_CACHE: dict[str, re.Pattern] = {}


def translate(scope: str) -> re.Pattern:
    """Translate a scope glob to a regex with path-aware semantics.

    `*` and `?` stay inside one path segment, `**` spans directories (including
    zero of them), and `[...]` classes pass through. fnmatch has none of this:
    it lets `*` cross `/`, so `src/pkg/*.py` silently governed everything under
    src/pkg, and it gives `**` no meaning at all, so `src/**/*.ts` matched
    nothing directly under src/.
    """
    out, i, n = [], 0, len(scope)
    while i < n:
        c = scope[i]
        if c == "*":
            if scope[i:i + 3] == "**/":
                out.append("(?:[^/]+/)*")   # zero or more directories
                i += 3
                continue
            if scope[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = scope.index("]", i + 1) if "]" in scope[i + 1:] else -1
            if j == -1:
                out.append(re.escape(c))
            else:
                body = scope[i + 1:j]
                body = ("^" + body[1:]) if body.startswith("!") else body
                out.append(f"[{body}]")
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out) + r"\Z")


def compiled(pattern: str) -> re.Pattern:
    regex = _CACHE.get(pattern)
    if regex is None:
        regex = _CACHE[pattern] = translate(pattern)
    return regex


def matches_anchored(relpath: str, pattern: str) -> bool:
    """`relpath` (POSIX, root-relative) against `pattern`, anchored at the
    root: `README.md` is the top-level README only. The guard's scopes differ on
    purpose — a scope with no "/" matches at any depth, the way .gitignore does,
    because rules in the wild depend on `*.py` meaning every Python file."""
    return bool(compiled(pattern).match(relpath))
