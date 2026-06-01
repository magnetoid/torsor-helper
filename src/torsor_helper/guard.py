from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

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
        note = store.read_note(path)
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
            if hit(node.module):
                out.append(_violation(rule, relpath, node.lineno, f"imports from forbidden module '{node.module}'"))
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
    )


_CHECKERS = {"forbid_import": _forbid_import, "forbid_pattern": _forbid_pattern}


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
            text = abs_path.read_text(encoding="utf-8")
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
