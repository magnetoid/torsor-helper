from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()
CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_models_config_roundtrips(tmp_path):
    paths = TorsorPaths(tmp_path)
    cfg = TorsorConfig()
    cfg.models.cheap = "claude-haiku-4-5"
    cfg.models.smart = "claude-opus-4-8"
    save_config(paths, cfg)
    loaded = load_config(paths)
    assert loaded.models.cheap == "claude-haiku-4-5"
    assert loaded.models.smart == "claude-opus-4-8"


def test_model_policy_names_tiers_and_work(tmp_path):
    store = _store(tmp_path)
    cfg = TorsorConfig()
    cfg.models.cheap = "haikutest"
    cfg.models.smart = "opustest"
    pol = ops.model_policy(store, cfg)
    assert "haikutest" in pol and "opustest" in pol
    assert "recall" in pol and "record_decision" in pol  # cheap lookups vs smart work


def test_write_model_policy_is_idempotent(tmp_path):
    store = _store(tmp_path)
    cfg = TorsorConfig()
    cfg.models.cheap = "haikutest"
    target = tmp_path / "AGENTS.md"
    ops.write_model_policy(store, cfg, target)
    ops.write_model_policy(store, cfg, target)
    text = target.read_text(encoding="utf-8")
    assert text.count("<!-- torsor:models -->") == 1  # block replaced, not duplicated


def test_model_policy_json_shape(tmp_path):
    store = _store(tmp_path)
    cfg = TorsorConfig()
    cfg.models.cheap = "ha"
    cfg.models.smart = "op"
    pol = ops.model_policy_json(store, cfg)
    assert pol["cheap"] == "ha" and pol["smart"] == "op"
    assert "recall" in pol["route"]["cheap"]
    assert isinstance(pol["route"]["smart"], list) and pol["route"]["smart"]


def test_cli_models_json_print(tmp_path):
    import json

    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["models", "--root", str(tmp_path), "--cheap", "ha", "--smart", "op"])
    r = runner.invoke(app, ["models", "--root", str(tmp_path), "--json"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["cheap"] == "ha" and "recall" in data["route"]["cheap"]


def test_cli_models_write_json_by_extension(tmp_path):
    import json

    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["models", "--root", str(tmp_path), "--cheap", "ha"])
    r = runner.invoke(app, ["models", "--root", str(tmp_path), "--write", "model-policy.json"])
    assert r.exit_code == 0
    data = json.loads((tmp_path / "model-policy.json").read_text(encoding="utf-8"))
    assert data["cheap"] == "ha" and "smart" in data["route"]


def test_cli_models_set_show_write(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    r = runner.invoke(app, ["models", "--root", str(tmp_path), "--cheap", "haikutest", "--smart", "opustest"])
    assert r.exit_code == 0, r.output
    show = runner.invoke(app, ["models", "--root", str(tmp_path)])
    assert "haikutest" in show.output and "opustest" in show.output
    w = runner.invoke(app, ["models", "--root", str(tmp_path), "--write", "AGENTS.md"])
    assert w.exit_code == 0
    assert "Model routing" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
