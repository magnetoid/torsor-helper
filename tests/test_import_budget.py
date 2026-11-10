"""What a `torsor` process loads before it does anything.

`torsor --help` and the PreToolUse guard hook run dozens of times per session;
the hook fires on every Edit. Both were importing numpy, the pydantic models and
every operations submodule at module scope in cli.py, so a hook that wanted to
check one file's text against a few rules paid for the whole search stack first.
Measured by module presence, not wall-clock, because the former is deterministic.
"""
import json
import subprocess
import sys

from typer.testing import CliRunner

from torsor_helper.cli import app

runner = CliRunner()

# Nothing on this list has any business in `--help`.
NOT_FOR_HELP = {
    "numpy", "pydantic", "yaml", "sqlite3",
    "torsor_helper.operations", "torsor_helper.db", "torsor_helper.search", "torsor_helper.embeddings",
    "torsor_helper.indexer", "torsor_helper.store", "torsor_helper.models", "torsor_helper.config",
    "torsor_helper.server",
}
# The hook needs config and the store (pydantic, yaml) but has no query to embed
# and no vector to rank. search.py itself rides in through the operations facade
# and is a millisecond once numpy is out of it; numpy is the cost worth pinning.
NOT_FOR_THE_EDIT_HOOK = {"numpy", "torsor_helper.server"}


def _modules_after(code: str, *, cwd=None, stdin: str = "") -> set[str]:
    proc = subprocess.run(
        [sys.executable, "-c", code + "\nimport sys, json; print(json.dumps(sorted(sys.modules)))"],
        input=stdin, capture_output=True, text=True, check=True, cwd=cwd,
    )
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def test_help_loads_none_of_the_core():
    loaded = _modules_after(
        "from typer.testing import CliRunner\n"
        "from torsor_helper.cli import app\n"
        "assert CliRunner().invoke(app, ['--help']).exit_code == 0"
    )
    assert not (loaded & NOT_FOR_HELP), sorted(loaded & NOT_FOR_HELP)


def test_the_edit_hook_does_not_load_the_search_stack(tmp_path):
    assert runner.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x.py", "new_string": "import os\n"}})
    loaded = _modules_after(
        "from typer.testing import CliRunner\n"
        "from torsor_helper.cli import app\n"
        f"r = CliRunner().invoke(app, ['hooks', 'run', 'pre-edit', '--root', {str(tmp_path)!r}], input={payload!r})\n"
        "assert r.exit_code == 0, r.output"
    )
    assert "torsor_helper.operations" in loaded  # the hook did run
    assert not (loaded & NOT_FOR_THE_EDIT_HOOK), sorted(loaded & NOT_FOR_THE_EDIT_HOOK)


def test_importing_operations_does_not_import_numpy():
    # Keeps the hook budget honest at the source: operations reaches numpy only
    # when a vector is actually packed or ranked.
    loaded = _modules_after("import torsor_helper.operations")
    assert "numpy" not in loaded
