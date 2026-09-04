from torsor_helper import languages
from torsor_helper.languages.modules import norm_module


def test_python_is_always_available_and_first():
    assert languages.is_available("python") is True
    assert ".py" in languages.source_extensions()


def test_spec_for_dispatches_on_suffix():
    assert languages.spec_for("pkg/x.py").name == "python"
    assert languages.spec_for("pkg/x.txt") is None


def test_python_extractor_is_the_registry_entry(tmp_path):
    symbols, edges = languages.extractor_for("a.py")("def f():\n    return g()\n", "a.py")
    assert [s.name for s in symbols] == ["f"]
    assert any(e.referenced_name == "g" and e.caller == "f" for e in edges)


def test_unavailable_language_is_skipped(monkeypatch):
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert languages.source_extensions() == (".py",)
    assert languages.spec_for("x.ts") is None


def test_norm_module_still_canonicalizes_python():
    assert norm_module("src/pkg/mod.py") == "pkg.mod"
    assert norm_module("pkg/dates.py") == "pkg.dates"
