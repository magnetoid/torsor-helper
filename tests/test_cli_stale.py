import json
from datetime import datetime

from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.models import Frontmatter
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _seed(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=lambda: datetime(2026, 7, 18, 12, 0, 0))
    store.write_note(store.paths.memory_dir / "n.md",
                     Frontmatter(type="observation", tags=["memory"]), "n", "See [[gone]].")
    return store


def test_stale_reports_findings(tmp_path):
    _seed(tmp_path)
    r = runner.invoke(app, ["stale", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "dangling_link" in r.stdout
    assert "gone" in r.stdout


def test_stale_json_and_strict_exit(tmp_path):
    _seed(tmp_path)
    r = runner.invoke(app, ["stale", "--root", str(tmp_path), "--json", "--strict"])
    assert r.exit_code == 1
    payload = json.loads(r.stdout)
    assert payload[0]["kind"] == "dangling_link"


def test_stale_clean_project(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    r = runner.invoke(app, ["stale", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "No staleness" in r.stdout


def test_stale_mark_and_unmark(tmp_path):
    store = _seed(tmp_path)
    r = runner.invoke(app, ["stale", "--root", str(tmp_path), "--mark"])
    assert "Marked 1 note" in r.stdout
    assert store.read_note(store.paths.memory_dir / "n.md").frontmatter.status == "stale"
    r = runner.invoke(app, ["stale", "--root", str(tmp_path), "--unmark"])
    assert "Unmarked 1 note" in r.stdout
    assert store.read_note(store.paths.memory_dir / "n.md").frontmatter.status == "active"
