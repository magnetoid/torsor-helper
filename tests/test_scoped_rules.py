"""`torsor rules --scoped`: one path-scoped Claude Code rule file per ADR under
.claude/rules/torsor/, so a rule only enters context when the agent touches a
file it governs (instead of one monolithic block in CLAUDE.md every session)."""
from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()

_ADR = """---
type: decision
status: accepted
rules:
- kind: forbid_import
  target: torsor_helper.server
  scope: src/torsor_helper/[!s]*.py
  severity: error
  message: core never imports an adapter
---

# ADR 0002: Adapters depend on core, never the reverse

## Decision
Core modules never import server.py or cli.py.
"""


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (store.paths.decisions_dir / "0002-adapters.md").write_text(_ADR, encoding="utf-8")
    return store


def test_scoped_rules_write_one_file_per_adr_with_paths_frontmatter(tmp_path):
    store = _store(tmp_path)

    written = ops.write_scoped_rules(store, TorsorConfig())

    files = {p.name: p for p in written}
    assert "0002-adapters.md" in files
    text = files["0002-adapters.md"].read_text(encoding="utf-8")
    assert text.startswith("---\npaths:\n")
    assert '"src/torsor_helper/[!s]*.py"' in text
    assert "forbid_import" in text and "torsor_helper.server" in text
    assert "core never imports an adapter" in text
    assert files["0002-adapters.md"].parent == store.paths.claude_rules_dir


def test_default_scope_becomes_a_recursive_python_glob(tmp_path):
    store = _store(tmp_path)
    adr = store.paths.decisions_dir / "0003-no-print.md"
    adr.write_text(
        "---\ntype: decision\nrules:\n- kind: forbid_pattern\n  target: print\\(\n---\n\n# ADR 0003: No print\n",
        encoding="utf-8",
    )

    written = {p.name: p for p in ops.write_scoped_rules(store, TorsorConfig())}

    assert '"**/*.py"' in written["0003-no-print.md"].read_text(encoding="utf-8")


def test_scoped_rules_dir_is_fully_managed_stale_files_are_removed(tmp_path):
    store = _store(tmp_path)
    store.paths.claude_rules_dir.mkdir(parents=True)
    stale = store.paths.claude_rules_dir / "0099-gone.md"
    stale.write_text("---\npaths:\n  - \"**/*.py\"\n---\nold\n", encoding="utf-8")

    ops.write_scoped_rules(store, TorsorConfig())

    assert not stale.exists()


def test_scoped_rules_never_touch_files_outside_the_torsor_dir(tmp_path):
    store = _store(tmp_path)
    mine = store.paths.claude_rules_dir.parent / "my-rules.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("keep me\n", encoding="utf-8")

    ops.write_scoped_rules(store, TorsorConfig())

    assert mine.read_text(encoding="utf-8") == "keep me\n"


def test_charter_principles_become_an_unscoped_rule_file(tmp_path):
    store = _store(tmp_path)
    store.paths.charter.write_text(
        "---\ntype: charter\n---\n\n# Charter\n\n## Non-negotiable principles\n\n- Markdown is the source of truth\n",
        encoding="utf-8",
    )

    written = {p.name: p for p in ops.write_scoped_rules(store, TorsorConfig())}

    text = written["principles.md"].read_text(encoding="utf-8")
    assert not text.startswith("---")  # no paths: → loads every session, like CLAUDE.md
    assert "Markdown is the source of truth" in text


def test_cli_rules_scoped_flag(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / ".torsor" / "architecture" / "decisions" / "0002-adapters.md").write_text(_ADR, encoding="utf-8")

    r = runner.invoke(app, ["rules", "--root", str(tmp_path), "--scoped"])

    assert r.exit_code == 0, r.output
    assert (tmp_path / ".claude" / "rules" / "torsor" / "0002-adapters.md").exists()
    assert ".claude/rules/torsor" in r.output
