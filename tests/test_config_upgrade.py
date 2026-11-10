"""A torsor.toml written by the previous release must still load.

ADR 0019 removed `[models]`, `budgets.practices_tokens` and
`automation.auto_snapshot_on_commit` — keys `torsor init` itself had written into
every project's torsor.toml. The config is strict on purpose (a typo must fail
loudly), so after the upgrade every command, every MCP tool and both hooks
failed on an existing project with "Extra inputs are not permitted". Found on
janus; the self-hosted repo had already dropped the keys by hand.
"""
import pytest
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.config import load_config, retired_config_keys
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()

# Verbatim from a project initialised by 0.8.0.
OLD_TOML = """\
version = 1

[budgets]
bootstrap_tokens = 2000
practices_tokens = 1200
max_items = 25

[models]
cheap = ""
smart = ""
fast = ""

[automation]
auto_handoff = true
auto_snapshot_on_commit = true
guard_on_edit = "advise"

[clean]
journal_retention_days = 90
"""


def _project(tmp_path, toml=OLD_TOML):
    paths = TorsorPaths(tmp_path)
    Store(paths).scaffold()
    paths.config_file.write_text(toml, encoding="utf-8")
    return paths


def test_a_toml_written_by_the_previous_release_still_loads(tmp_path):
    config = load_config(_project(tmp_path))
    assert config.budgets.max_items == 25          # the live keys around the retired ones survive
    assert config.automation.guard_on_edit == "advise"


def test_the_retired_keys_are_named_so_they_can_be_deleted(tmp_path):
    assert retired_config_keys(_project(tmp_path)) == [
        "budgets.practices_tokens", "models", "automation.auto_snapshot_on_commit",
    ]
    assert retired_config_keys(_project(tmp_path, "version = 1\n")) == []


def test_a_typo_is_still_an_error(tmp_path):
    # Tolerance is for the keys a previous torsor wrote, not for anything unknown.
    with pytest.raises(ValueError):
        load_config(_project(tmp_path, "version = 1\n\n[budgets]\npractice_tokens = 3\n"))


def test_doctor_warns_about_retired_keys_without_failing(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "warn  config" in res.output
    assert "practices_tokens" in res.output and "torsor.toml" in res.output


def test_the_edit_hook_survives_the_upgrade(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["hooks", "run", "pre-edit", "--root", str(tmp_path)],
                        input='{"tool_name": "Edit", "tool_input": {"file_path": "x.py", "new_string": "x"}}')
    assert res.exit_code == 0, res.output
