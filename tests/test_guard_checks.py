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


def test_violation_carries_severity_and_rule_id():
    rule = Rule(kind="forbid_import", target="requests", severity="error", source="ADR 2")
    vs = violations_for_file("app.py", "import requests\n", rule)
    assert vs[0].severity == "error"
    assert vs[0].rule_id == "forbid_import:requests"  # default id from kind:target


def test_strict_failures_threshold():
    from torsor_helper.guard import strict_failures
    from torsor_helper.models import Violation

    vs = [
        Violation(rule_kind="forbid_import", target="a", file="x.py", message="m", source="s", severity="hint"),
        Violation(rule_kind="forbid_import", target="b", file="y.py", message="m", source="s", severity="error"),
    ]
    assert len(strict_failures(vs, None)) == 2          # no threshold → any violation fails
    assert len(strict_failures(vs, "warning")) == 1     # only the error clears the bar
    assert len(strict_failures(vs, "hint")) == 2


def test_require_import_flags_missing_seam():
    rule = Rule(kind="require_import", target="app.auth", scope="handlers/*.py", source="ADR")
    vs = violations_for_file("handlers/x.py", "import os\n", rule)
    assert len(vs) == 1
    assert vs[0].line == 0  # one file-level violation, not per-node


def test_require_import_satisfied_by_any_import_form():
    rule = Rule(kind="require_import", target="app.auth", source="ADR")
    assert violations_for_file("h.py", "from app.auth import login\n", rule) == []
    assert violations_for_file("h.py", "from app import auth\n", rule) == []
    assert violations_for_file("h.py", "import app.auth\n", rule) == []


def test_require_import_skips_syntax_errors():
    rule = Rule(kind="require_import", target="app.auth", source="ADR")
    assert violations_for_file("h.py", "def broken(:\n", rule) == []


def test_forbid_layer_import_flags_cross_layer_only():
    rule = Rule(kind="forbid_layer_import", target=r"features\.b(\.|$)", scope="features/a/*.py", source="ADR")
    assert len(violations_for_file("features/a/x.py", "from features.b import thing\n", rule)) == 1
    assert len(violations_for_file("features/a/x.py", "import features.b.deep\n", rule)) == 1
    assert violations_for_file("features/a/x.py", "from features.c import thing\n", rule) == []


def test_forbid_layer_import_bad_regex_degrades_to_skip():
    rule = Rule(kind="forbid_layer_import", target="features.[", scope="*.py", source="ADR")
    assert violations_for_file("a.py", "import features.b\n", rule) == []


def test_require_import_only_applies_in_scope(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    adr = store.paths.decisions_dir / "0002-handlers-need-auth.md"
    adr.write_text(
        "---\ntype: decision\nrules:\n  - kind: require_import\n    target: app.auth\n"
        "    scope: 'handlers/*.py'\n---\n\n# ADR 0002: handlers need auth\n\nb\n"
    )
    (tmp_path / "handlers").mkdir()
    (tmp_path / "handlers" / "h.py").write_text("import os\n")  # in scope, missing seam
    (tmp_path / "util.py").write_text("import os\n")           # out of scope
    files = {v.file for v in check_drift(store, ["handlers/h.py", "util.py"])}
    assert "handlers/h.py" in files
    assert "util.py" not in files


def test_forbid_import_resolves_relative_imports():
    # `from . import server` inside the package is the idiomatic way an agent
    # writes the forbidden import — it must not bypass the rule.
    rule = Rule(kind="forbid_import", target="torsor_helper.server", source="ADR 2")
    assert len(violations_for_file("src/torsor_helper/operations.py", "from . import server\n", rule)) == 1
    assert len(violations_for_file("src/torsor_helper/operations.py", "from .server import run\n", rule)) == 1
    # the same statement in a *different* package must NOT match
    assert violations_for_file("src/other/x.py", "from .server import run\n", rule) == []


def test_require_import_not_satisfied_by_unrelated_relative_import():
    rule = Rule(kind="require_import", target="audit", source="ADR")
    # `from .audit import log` in pkg/ resolves to pkg.audit, not top-level audit
    assert len(violations_for_file("pkg/x.py", "from .audit import log\n", rule)) == 1


def test_require_import_satisfied_by_relative_import():
    rule = Rule(kind="require_import", target="torsor_helper.auth", source="ADR")
    assert violations_for_file("src/torsor_helper/x.py", "from . import auth\n", rule) == []


def test_forbid_layer_import_resolves_relative_imports():
    rule = Rule(kind="forbid_layer_import", target=r"features\.b(\.|$)", scope="features/a/*.py", source="ADR")
    assert len(violations_for_file("features/a/x.py", "from ..b import api\n", rule)) == 1


def test_check_drift_reads_bom_files(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    adr = store.paths.decisions_dir / "0002-no-requests.md"
    adr.write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n    scope: '*.py'\n---\n\n# ADR\n\nb\n"
    )
    (tmp_path / "bom.py").write_text("\ufeffimport requests\n", encoding="utf-8")
    vs = check_drift(store, ["bom.py"])
    assert any(v.file == "bom.py" for v in vs)


def test_check_drift_survives_malformed_decision_note(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    good = store.paths.decisions_dir / "0002-no-requests.md"
    good.write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n    scope: '*.py'\n---\n\n# ADR\n\nb\n"
    )
    (store.paths.decisions_dir / "0003-broken.md").write_bytes(b"\xff\xfe not utf-8")
    (tmp_path / "app.py").write_text("import requests\n")
    vs = check_drift(store, ["app.py"])  # must not raise; good rules still apply
    assert any(v.file == "app.py" for v in vs)
