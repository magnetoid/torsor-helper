from __future__ import annotations

import ast
import re
from pathlib import Path

from torsor_helper.cartographer import absolute_from_module
from torsor_helper.models import Rule, Violation
from torsor_helper.store import Store
from torsor_helper.paths import contained


def load_rules_by_note(store: Store) -> list[tuple[Path, str, list[Rule]]]:
    """(note path, note title, its rules) for every ADR / system-patterns note
    that declares a `rules:` block — the grouping the scoped-rules exporter
    needs, and the single place rule parsing happens."""
    notes = []
    if store.paths.decisions_dir.exists():
        notes.extend(sorted(store.paths.decisions_dir.glob("*.md")))
    if store.paths.system_patterns.exists():
        notes.append(store.paths.system_patterns)

    out: list[tuple[Path, str, list[Rule]]] = []
    for path in notes:
        try:
            note = store.read_note(path)
        except (OSError, UnicodeDecodeError):
            continue  # malformed note: skip, never fatal (same contract as malformed rules)
        raw = getattr(note.frontmatter, "rules", None)
        if not isinstance(raw, list):
            continue
        rules: list[Rule] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                rules.append(Rule.model_validate({**item, "source": note.title}))
            except Exception:
                continue  # malformed rule: skip, never fatal
        if rules:
            out.append((path, note.title, rules))
    return out


_SCOPE_CACHE: dict[str, re.Pattern] = {}


def _scope_regex(scope: str) -> re.Pattern:
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


def scope_matches(relpath: str, scope: str) -> bool:
    """Does `relpath` fall inside `scope`?

    A scope containing no "/" matches at any depth, the way a .gitignore
    pattern does — `scope: "*.py"` has always meant "Python files" and rules in
    the wild depend on it. A scope with a "/" is anchored at the repo root.
    """
    pattern = _SCOPE_CACHE.get(scope)
    if pattern is None:
        pattern = _SCOPE_CACHE[scope] = _scope_regex(scope)
    if "/" not in scope:
        return bool(pattern.match(relpath.rsplit("/", 1)[-1]))
    return bool(pattern.match(relpath))


def load_rules(store: Store) -> list[Rule]:
    return [rule for _path, _title, rules in load_rules_by_note(store) for rule in rules]


def _forbid_import(relpath: str, text: str, rule: Rule) -> list[Violation]:
    if not relpath.endswith(".py"):
        return _forbid_import_specifiers(relpath, text, rule)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    target = rule.target
    out: list[Violation] = []

    def hit(name: str | None) -> bool:
        return bool(name) and (name == target or name.startswith(target + "."))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if hit(alias.name):
                    out.append(_violation(rule, relpath, node.lineno, f"imports forbidden module '{alias.name}'"))
        elif isinstance(node, ast.ImportFrom):
            # Level-aware: `from . import server` inside the package is the
            # idiomatic way to write a forbidden import — resolve it to absolute
            # dotted form so relative imports can't bypass the rule.
            base = absolute_from_module(node, relpath)
            if hit(base):
                out.append(_violation(rule, relpath, node.lineno, f"imports from forbidden module '{base}'"))
                continue
            # `from pkg import submod` puts the submodule in names, not in `base`.
            for alias in node.names:
                full = f"{base}.{alias.name}" if base else alias.name
                if hit(full):
                    out.append(_violation(rule, relpath, node.lineno, f"imports forbidden module '{full}'"))
                    break  # one violation per import statement
    return out


def _forbid_import_specifiers(relpath: str, text: str, rule: Rule) -> list[Violation]:
    """Non-Python: match the rule's target as a prefix of the import specifier
    string ('lodash', '../internal/db', 'example.com/app/internal'). Silent
    when the language isn't available — never an error."""
    from torsor_helper import languages

    target = rule.target.rstrip("/")
    if not target:
        return []  # an empty target would prefix-match every specifier
    out: list[Violation] = []
    for spec, line in languages.import_specifiers(relpath, text):
        if spec == target or spec.startswith(target + "/") or spec.startswith(target + "."):
            out.append(_violation(rule, relpath, line, f"imports forbidden module '{spec}'"))
    return out


def _imported_modules(tree: ast.Module, relpath: str) -> list[tuple[str, int]]:
    """All imported module strings (absolute dotted form, relative imports
    resolved against `relpath`) with their line numbers, including the
    `from pkg import submod` submodule form (mirrors _forbid_import resolution)."""
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from_module(node, relpath)
            if base:
                out.append((base, node.lineno))
            for alias in node.names:
                out.append((f"{base}.{alias.name}" if base else alias.name, node.lineno))
    return out


def _require_import(relpath: str, text: str, rule: Rule) -> list[Violation]:
    """Mandatory-seam check: emit ONE file-level violation when a required import
    is ABSENT (inverts the usual find-a-match model)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    target = rule.target
    present = any(m == target or m.startswith(target + ".") for m, _ in _imported_modules(tree, relpath))
    if present:
        return []
    return [_violation(rule, relpath, 0, f"required import '{target}' is missing")]


def _forbid_layer_import(relpath: str, text: str, rule: Rule) -> list[Violation]:
    """Layering check: forbid importing any module whose dotted path matches the
    `target` regex (e.g. 'features\\.b(\\.|$)'). Use the rule's scope as the
    'from' selector ('files matching scope X may not import Y')."""
    try:
        pattern = re.compile(rule.target)
    except re.error:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if pattern.search(alias.name):
                    out.append(_violation(rule, relpath, node.lineno, f"layer import '{alias.name}' is forbidden here"))
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from_module(node, relpath)
            candidates = ([base] if base else []) + [
                (f"{base}.{alias.name}" if base else alias.name) for alias in node.names
            ]
            for cand in candidates:
                if cand and pattern.search(cand):
                    out.append(_violation(rule, relpath, node.lineno, f"layer import '{cand}' is forbidden here"))
                    break  # one violation per import statement
    return out


def _forbid_pattern(relpath: str, text: str, rule: Rule) -> list[Violation]:
    try:
        pattern = re.compile(rule.target)
    except re.error:
        return []
    out: list[Violation] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            out.append(_violation(rule, relpath, i, f"matches forbidden pattern '{rule.target}'"))
    return out


def _violation(rule: Rule, relpath: str, line: int, default_msg: str) -> Violation:
    return Violation(
        rule_kind=rule.kind, target=rule.target, file=relpath, line=line,
        message=rule.message or default_msg, source=rule.source,
        severity=rule.severity, rule_id=rule.rule_id or f"{rule.kind}:{rule.target}",
    )


_SEVERITY_ORDER = {"hint": 0, "info": 1, "warning": 2, "error": 3}
SEVERITIES = tuple(_SEVERITY_ORDER)


def strict_failures(violations, threshold: str | None = None) -> list[Violation]:
    """Violations that should fail --strict: all of them when threshold is None
    (back-compatible 'fail on any'), else only those at/above the threshold."""
    if threshold is None:
        return list(violations)
    cutoff = _SEVERITY_ORDER.get(threshold, 0)
    return [v for v in violations if _SEVERITY_ORDER.get(v.severity, 2) >= cutoff]


_CHECKERS = {
    "forbid_import": _forbid_import,
    "forbid_pattern": _forbid_pattern,
    "require_import": _require_import,
    "forbid_layer_import": _forbid_layer_import,
}


def violations_for_file(relpath: str, text: str, rule: Rule) -> list[Violation]:
    checker = _CHECKERS.get(rule.kind)
    if checker is None:
        return []
    return checker(relpath, text, rule)


def check_drift(store: Store, files) -> list[Violation]:
    rules = load_rules(store)
    if not rules:
        return []
    root = store.paths.root
    out: list[Violation] = []
    for raw in files:
        abs_path = contained(root, raw)
        if abs_path is None:
            continue  # outside the project — not ours to read, let alone judge
        try:
            # utf-8-sig: a BOM would make ast.parse fail and the file silently pass
            text = abs_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        relpath = abs_path.relative_to(Path(root).resolve()).as_posix()
        for rule in rules:
            if scope_matches(relpath, rule.scope):
                out.extend(violations_for_file(relpath, text, rule))
    return out
