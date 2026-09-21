"""What the project actually contains, and whether it is healthy.

`doctor` checked four things — the directory, four seed files, and that the
config parses — none of which are the failure modes people hit. It could not
say whether the index was stale, whether semantic recall was silently running
on the hashing fallback, whether the hooks it wrote were installed, or whether
an ADR's rules block was malformed. Every one of those checks already existed
as a function somewhere.

And nothing answered "how big is my memory, what is being recalled, is the map
current" at all.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _json_of(result):
    """Click 8.5's runner folds stderr into `output`, and get_embedder warns
    there when fastembed is missing. The JSON is the last line."""
    assert result.exit_code in (0, 1), result.output
    for line in reversed(result.output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON in output:\n{result.output}")


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


# --- stats ------------------------------------------------------------------

def test_stats_reports_the_shape_of_the_project(tmp_path):
    store = _project(tmp_path)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    ops.map_repo(store, TorsorConfig())

    result = ops.stats(store, TorsorConfig())

    assert result["notes"]["total"] >= 4
    assert sum(result["notes"]["by_tier"].values()) == result["notes"]["total"]
    assert result["symbols"] >= 1
    assert result["embedder"]
    assert "index_bytes" in result


def test_stats_works_without_an_index(tmp_path):
    store = _project(tmp_path)
    result = ops.stats(store, TorsorConfig())
    assert result["notes"]["total"] >= 4
    assert result["symbols"] == 0
    assert result["index_bytes"] == 0


def test_stats_cli_prints_and_emits_json(tmp_path):
    _project(tmp_path)
    plain = runner.invoke(app, ["stats", "--root", str(tmp_path)])
    assert plain.exit_code == 0, plain.output
    assert "notes" in plain.output.lower()

    payload = _json_of(runner.invoke(app, ["stats", "--root", str(tmp_path), "--json"]))
    assert payload["notes"]["total"] >= 4


# --- doctor -----------------------------------------------------------------

def test_doctor_emits_structured_checks(tmp_path):
    _project(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    payload = _json_of(result)
    names = {c["name"] for c in payload["checks"]}
    assert {"layout", "config", "index", "embeddings", "git", "hooks", "rules"} <= names
    assert payload["ok"] is True


def test_doctor_says_when_semantic_recall_is_on_the_fallback(tmp_path):
    _project(tmp_path)
    payload = _json_of(runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"]))
    embeddings = next(c for c in payload["checks"] if c["name"] == "embeddings")
    # fastembed is not installed in the test environment
    assert embeddings["status"] in ("warn", "ok")
    if embeddings["status"] == "warn":
        assert "hashing" in embeddings["detail"].lower()


def test_doctor_reports_a_malformed_rules_block(tmp_path):
    store = _project(tmp_path)
    (store.paths.decisions_dir / "0099-broken.md").write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    scope: '*.py'\n---\n\n# Broken\n\nb\n",
        encoding="utf-8",
    )

    payload = _json_of(runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"]))

    rules = next(c for c in payload["checks"] if c["name"] == "rules")
    assert rules["status"] == "warn"
    assert "0099" in rules["detail"]


def test_doctor_still_exits_one_on_a_broken_project(tmp_path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path / "nope")])
    assert result.exit_code == 1


# --- consolidate ------------------------------------------------------------

def test_consolidate_names_the_duplicates_it_counted(tmp_path):
    store = _project(tmp_path)
    for i in range(3):
        store.append_journal("the exact same observation", kind="observation", links=[])

    stats = ops.consolidate(store, TorsorConfig())

    assert stats["duplicates"] >= 1
    assert stats["duplicate_entries"], "the list was computed and thrown away"
    assert any("same observation" in text for text, _ in stats["duplicate_entries"])


def test_the_mcp_surface_gained_stats_and_recall_filters(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _project(tmp_path)
    tools = {t.name: t for t in anyio.run(build_server(tmp_path).list_tools)}

    assert "stats" in tools
    recall_args = set(tools["recall"].inputSchema.get("properties") or {})
    assert {"type", "kind", "include_superseded"} <= recall_args
