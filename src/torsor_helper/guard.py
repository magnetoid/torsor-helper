from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

from torsor_helper.cartographer import absolute_from_module
from torsor_helper.models import Rule, Violation
from torsor_helper.store import Store


def load_rules(store: Store) -> list[Rule]:
    notes = []
    if store.paths.decisions_dir.exists():
        notes.extend(sorted(store.paths.decisions_dir.glob("*.md")))
    if store.paths.system_patterns.exists():
        notes.append(store.paths.system_patterns)

    rules: list[Rule] = []
    for path in notes:
        try:
            note = store.read_note(path)
        except (OSError, UnicodeDecodeError):
            continue  # malformed note: skip, never fatal (same contract as malformed rules)
        raw = getattr(note.frontmatter, "rules", None)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                rule = Rule.model_validate({**item, "source": note.title})
            except Exception:
                continue  # malformed rule: skip, never fatal
            rules.append(rule)
    return rules


def _forbid_import(relpath: str, text: str, rule: Rule) -> list[Violation]:
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
        path = Path(raw)
        abs_path = path if path.is_absolute() else root / path
        try:
            # utf-8-sig: a BOM would make ast.parse fail and the file silently pass
            text = abs_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            relpath = abs_path.relative_to(root).as_posix()
        except ValueError:
            relpath = abs_path.name
        for rule in rules:
            if fnmatch.fnmatch(relpath, rule.scope):
                out.extend(violations_for_file(relpath, text, rule))
    return out
