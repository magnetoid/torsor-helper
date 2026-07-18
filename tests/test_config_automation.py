from pathlib import Path

from torsor_helper.config import AutomationConfig, TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths


def test_automation_defaults():
    cfg = TorsorConfig()
    # Capture behaviors default ON (installing hooks is itself the opt-in, and
    # each only touches .torsor/ Markdown or the disposable index).
    assert cfg.automation.auto_handoff is True
    assert cfg.automation.auto_map_on_commit is True
    assert cfg.automation.auto_snapshot_on_commit is True
    # The one behavior that could surprise-block a push defaults OFF.
    assert cfg.automation.guard_on_push is False
    # Transcript enrichment is opt-in.
    assert cfg.automation.parse_transcript is False


def test_automation_round_trips_through_toml(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    paths.base.mkdir(parents=True)
    cfg = TorsorConfig()
    cfg.automation.auto_handoff = False
    cfg.automation.guard_on_push = True
    save_config(paths, cfg)
    loaded = load_config(paths)
    assert loaded.automation.auto_handoff is False
    assert loaded.automation.guard_on_push is True


def test_automation_partial_config_validates(tmp_path: Path):
    # A config file that omits [automation] entirely still validates with defaults.
    paths = TorsorPaths(tmp_path)
    paths.base.mkdir(parents=True)
    paths.config_file.write_text("version = 1\n")
    loaded = load_config(paths)
    assert isinstance(loaded.automation, AutomationConfig)
    assert loaded.automation.auto_map_on_commit is True


def test_claude_settings_paths(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    assert paths.claude_settings == tmp_path / ".claude" / "settings.json"
    assert paths.claude_settings_local == tmp_path / ".claude" / "settings.local.json"
