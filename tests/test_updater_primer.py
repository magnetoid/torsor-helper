from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper import updater
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 11, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


# ---- updater ----

def test_detect_install_method_returns_known_value():
    assert updater.detect_install_method() in ("uv-tool", "pipx", "pip", "dev")


def test_update_command_per_method():
    assert updater.update_command("uv-tool") == ["uv", "tool", "upgrade", "torsor-helper"]
    assert updater.update_command("pipx") == ["pipx", "upgrade", "torsor-helper"]
    assert updater.update_command("pip")[-2:] == ["--upgrade", "torsor-helper"]
    assert updater.update_command("dev") is None


def test_manual_hint_for_dev():
    assert "git pull" in updater.manual_hint("dev")
    assert "uv tool upgrade" in updater.manual_hint("unknown")


# ---- primer (token saver) ----

def test_project_primer_contains_charter_and_playbook(tmp_path):
    store = _store(tmp_path)
    out = ops.project_primer(store, TorsorConfig())
    assert "Project primer" in out
    assert "What this project is" in out
    assert "Work token-efficiently" in out


def test_project_primer_respects_budget(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    small = ops.project_primer(store, config, max_tokens=100)
    assert len(small) <= 100 * config.budgets.chars_per_token + 20  # truncation marker slack


def test_write_primer_block_is_idempotent(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    target = tmp_path / "AGENTS.md"
    target.write_text("# My agents file\n\nkeep me\n")
    ops.write_primer_block(store, config, target)
    once = target.read_text()
    ops.write_primer_block(store, config, target)
    twice = target.read_text()
    assert once == twice
    assert twice.count("<!-- torsor:primer -->") == 1
    assert "keep me" in twice


def test_primer_and_rules_blocks_coexist(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    target = tmp_path / "AGENTS.md"
    ops.write_rules_block(store, config, target)
    ops.write_primer_block(store, config, target)
    text = target.read_text()
    assert "<!-- torsor:rules -->" in text and "<!-- torsor:primer -->" in text
