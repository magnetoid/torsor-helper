from __future__ import annotations

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
