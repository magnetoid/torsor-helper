import pytest
from typer.testing import CliRunner

from torsor_helper import languages
from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.coach import health
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def test_doctor_lists_language_availability(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    r = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "python: ready" in r.output
    assert "typescript: install torsor-helper[languages]" in r.output


def test_map_summary_reports_per_language_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    r = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert "python 1" in r.output


def test_map_summary_flags_a_language_the_extra_cannot_see(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    for i in range(3):
        (tmp_path / f"m{i}.ts").write_text("export const x = 1;\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")

    store = Store(TorsorPaths(tmp_path))
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["languages"]["unavailable"] == {"typescript": 3}

    r = runner.invoke(app, ["map", "--root", str(tmp_path), "--force"])
    assert "typescript 3 — install torsor-helper[languages]" in r.output


def test_map_summary_omits_languages_with_no_files(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")

    store = Store(TorsorPaths(tmp_path))
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["languages"]["unavailable"] == {}

    r = runner.invoke(app, ["map", "--root", str(tmp_path), "--force"])
    assert "install torsor-helper[languages]" not in r.output


def test_map_summary_has_no_unavailable_entry_when_the_extra_is_installed(tmp_path):
    if not languages.is_available("typescript"):
        pytest.skip("needs [languages] extra")
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "a.ts").write_text("export const x = 1;\n")
    store = Store(TorsorPaths(tmp_path))
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["languages"]["unavailable"] == {}


def test_uncharted_language_rec_when_extra_missing(tmp_path, monkeypatch):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    for i in range(6):
        (tmp_path / "src" / f"m{i}.ts").write_text("export const x = 1;\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    recs = health.check_uncharted_language(store)
    assert len(recs) == 1 and recs[0].kind == "uncharted_language"
    assert "typescript" in recs[0].message and "[languages]" in recs[0].action


def test_no_uncharted_language_rec_below_threshold_or_when_available(tmp_path, monkeypatch):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "a.ts").write_text("export const x = 1;\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert health.check_uncharted_language(store) == []
    monkeypatch.setattr(languages, "is_available", lambda name: True)
    for i in range(6):
        (tmp_path / f"m{i}.ts").write_text("export const x = 1;\n")
    assert health.check_uncharted_language(store) == []
