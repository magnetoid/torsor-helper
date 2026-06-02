from datetime import datetime

from torsor_helper.guard import check_drift, violations_for_file
from torsor_helper.models import Rule
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def test_forbid_import_flags_matching_import():
    rule = Rule(kind="forbid_import", target="requests", scope="*.py", message="no requests", source="ADR 2")
    text = "import os\nimport requests\nfrom requests.sessions import Session\n"
    vs = violations_for_file("app.py", text, rule)
    assert len(vs) == 2
    assert vs[0].line == 2 and vs[0].file == "app.py" and vs[0].source == "ADR 2"


def test_forbid_import_ignores_unrelated_and_syntax_errors():
    rule = Rule(kind="forbid_import", target="requests", source="ADR 2")
    assert violations_for_file("a.py", "import os\nfrom json import loads\n", rule) == []
    assert violations_for_file("a.py", "def broken(:\n", rule) == []


def test_forbid_pattern_flags_regex_per_line():
    rule = Rule(kind="forbid_pattern", target=r"TODO|FIXME", scope="*.py", message="no TODOs", source="ADR 5")
    text = "x = 1\n# TODO: later\ny = 2  # FIXME\n"
    vs = violations_for_file("a.py", text, rule)
    assert {v.line for v in vs} == {2, 3}


def test_check_drift_applies_scoped_rules(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    adr = store.paths.decisions_dir / "0002-no-requests-in-domain.md"
    adr.write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n    scope: 'domain/*.py'\n---\n\n# ADR 0002: x\n\nb\n"
    )
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    (tmp_path / "infra.py").write_text("import requests\n")
    vs = check_drift(store, ["domain/svc.py", "infra.py"])
    files = {v.file for v in vs}
    assert "domain/svc.py" in files
    assert "infra.py" not in files


def test_forbid_import_flags_from_package_import_submodule():
    # `from torsor_helper import operations` — the dominant internal-import form.
    rule = Rule(kind="forbid_import", target="torsor_helper.operations", source="ADR")
    vs = violations_for_file("guard.py", "from torsor_helper import operations\n", rule)
    assert len(vs) == 1 and vs[0].line == 1


def test_forbid_import_flags_from_package_import_submodule_aliased():
    rule = Rule(kind="forbid_import", target="torsor_helper.db", source="ADR")
    vs = violations_for_file("x.py", "from torsor_helper import cartographer, db, guard\n", rule)
    assert len(vs) == 1  # one violation per statement, flagged via the `db` name


def test_forbid_import_module_forbidden_counts_once():
    rule = Rule(kind="forbid_import", target="requests", source="ADR")
    vs = violations_for_file("x.py", "from requests import get, post\n", rule)
    assert len(vs) == 1  # module itself forbidden -> single violation, not per-name
