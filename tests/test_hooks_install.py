"""Pure-module tests for the managed git-hook writer: marker-delimited block,
exec bit, idempotency, foreign-content preservation, surgical removal."""
import os

from torsor_helper import hooks


def test_creates_hook_with_shebang_and_exec_bit(tmp_path):
    block = hooks.post_commit_script(str(tmp_path))
    target = hooks.write_git_hook(tmp_path, "post-commit", block)
    assert target.exists()
    text = target.read_text()
    assert text.startswith("#!")
    assert "torsor hooks run post-commit" in text
    assert os.access(target, os.X_OK)  # executable


def test_reinstall_is_idempotent(tmp_path):
    block = hooks.post_commit_script(str(tmp_path))
    hooks.write_git_hook(tmp_path, "post-commit", block)
    hooks.write_git_hook(tmp_path, "post-commit", block)
    text = (tmp_path / "post-commit").read_text()
    assert text.count(hooks._GIT_START) == 1  # exactly one managed block


def test_preserves_pre_existing_user_hook(tmp_path):
    target = tmp_path / "post-commit"
    target.write_text("#!/bin/sh\necho 'my custom hook'\n")
    hooks.write_git_hook(tmp_path, "post-commit", hooks.post_commit_script(str(tmp_path)))
    text = target.read_text()
    assert "echo 'my custom hook'" in text  # foreign body preserved
    assert "torsor hooks run post-commit" in text


def test_uninstall_removes_only_the_block(tmp_path):
    target = tmp_path / "post-commit"
    target.write_text("#!/bin/sh\necho 'mine'\n")
    hooks.write_git_hook(tmp_path, "post-commit", hooks.post_commit_script(str(tmp_path)))
    hooks.write_git_hook(tmp_path, "post-commit", "", remove=True)
    text = target.read_text()
    assert "echo 'mine'" in text
    assert "torsor hooks run" not in text


def test_uninstall_deletes_file_when_only_shebang_remains(tmp_path):
    hooks.write_git_hook(tmp_path, "post-commit", hooks.post_commit_script(str(tmp_path)))
    hooks.write_git_hook(tmp_path, "post-commit", "", remove=True)
    assert not (tmp_path / "post-commit").exists()


def test_uninstall_absent_file_is_noop(tmp_path):
    assert hooks.write_git_hook(tmp_path, "post-commit", "", remove=True) is None
