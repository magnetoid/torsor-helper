"""resolve_hooks_dir honors real git layout (incl. core.hooksPath) and returns
None outside a repo."""
import subprocess

from torsor_helper import hooks


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def test_returns_none_outside_git_repo(tmp_path):
    assert hooks.resolve_hooks_dir(tmp_path) is None


def test_default_hooks_dir(tmp_path):
    _git(tmp_path, "init")
    hooks_dir = hooks.resolve_hooks_dir(tmp_path)
    assert hooks_dir is not None
    assert hooks_dir.name == "hooks"
    assert hooks_dir.resolve() == (tmp_path / ".git" / "hooks").resolve()


def test_honors_core_hooks_path(tmp_path):
    _git(tmp_path, "init")
    custom = tmp_path / "my-hooks"
    custom.mkdir()
    _git(tmp_path, "config", "core.hooksPath", str(custom))
    hooks_dir = hooks.resolve_hooks_dir(tmp_path)
    assert hooks_dir is not None
    assert hooks_dir.resolve() == custom.resolve()
