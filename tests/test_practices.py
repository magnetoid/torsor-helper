import re
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper import practices
from torsor_helper.config import TorsorConfig
from torsor_helper.guard import check_drift
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 11, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_every_pack_is_well_formed():
    for lang in practices.available_languages():
        pack = practices.pack(lang)
        assert pack["label"] and pack["practices"]
        for item in pack["practices"]:
            assert item["title"] and item["rationale"]
            assert isinstance(item["ai_prone"], bool)
            rule = item["rule"]
            if rule is not None:
                assert rule["kind"] == "forbid_pattern"
                re.compile(rule["target"])  # every shipped regex must compile
                assert rule["severity"] in ("hint", "info", "warning", "error")
                assert rule["message"]


def test_every_pack_has_enforceable_rules():
    for lang in practices.available_languages():
        assert any(item["rule"] for item in practices.pack(lang)["practices"])


def test_detect_languages_by_extension(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    (tmp_path / "c.ts").write_text("const z = 3\n")
    detected = practices.detect_languages(tmp_path)
    assert detected[0] == "python"  # most files
    assert "typescript" in detected


def test_render_lists_titles():
    out = practices.render("python")
    assert "bare `except:`" in out
    assert "guard-enforced" in out and "principle" in out


def test_adopt_records_adr_that_guard_enforces(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    result = ops.adopt_practices(store, config, "python")
    assert result["adopted"]

    (tmp_path / "app.py").write_text("try:\n    x()\nexcept:\n    pass\n")
    violations = check_drift(store, ["app.py"])
    assert any("except" in v.message for v in violations)  # the pack rule fires


def test_adopt_twice_is_refused(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    assert ops.adopt_practices(store, config, "python")["adopted"]
    second = ops.adopt_practices(store, config, "python")
    assert not second["adopted"]
    assert "Already adopted" in second["message"]


def test_adopt_unknown_language(tmp_path):
    store = _store(tmp_path)
    result = ops.adopt_practices(store, TorsorConfig(), "cobol")
    assert not result["adopted"]
    assert "Available:" in result["message"]


def test_list_practices_autodetects(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "m.py").write_text("x = 1\n")
    out = ops.list_practices(store, TorsorConfig())
    assert "Python best practices" in out


def test_python_regexes_do_not_overfire():
    # the eval ban must not match method calls like model.eval()
    rule = next(
        item["rule"] for item in practices.pack("python")["practices"]
        if item["rule"] and "eval" in item["rule"]["target"]
    )
    pattern = re.compile(rule["target"])
    assert not pattern.search("model.eval()")
    assert pattern.search("eval(user_input)")
