from datetime import datetime

from torsor_helper.guard import load_rules
from torsor_helper.models import Rule
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_load_rules_reads_adr_frontmatter(tmp_path):
    store = _store(tmp_path)
    adr = store.paths.decisions_dir / "0002-no-requests-in-domain.md"
    adr.write_text(
        "---\n"
        "type: decision\n"
        "status: accepted\n"
        "rules:\n"
        "  - kind: forbid_import\n"
        "    target: requests\n"
        "    scope: 'domain/*.py'\n"
        "    message: domain must stay framework-free\n"
        "---\n\n# ADR 0002: No requests in domain\n\nbody\n"
    )
    rules = load_rules(store)
    assert any(r.kind == "forbid_import" and r.target == "requests" for r in rules)
    rule = next(r for r in rules if r.target == "requests")
    assert rule.scope == "domain/*.py"
    assert rule.source
    assert isinstance(rule, Rule)


def test_load_rules_skips_malformed(tmp_path):
    store = _store(tmp_path)
    adr = store.paths.decisions_dir / "0003-bad.md"
    adr.write_text("---\ntype: decision\nrules:\n  - notakey: x\n---\n\n# ADR 0003: Bad\n\nb\n")
    rules = load_rules(store)
    assert all(r.source != "ADR 0003: Bad" for r in rules)
