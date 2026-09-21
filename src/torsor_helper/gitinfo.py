from __future__ import annotations

import subprocess
from pathlib import Path

from torsor_helper import languages

# Every git call torsor makes goes through here. A leaf: it imports only the
# language registry (for the source-extension filter) and never reaches back
# into operations. Git is optional everywhere — a missing binary, a directory
# that is not a repo, or a timeout all degrade to an empty answer rather than an
# exception, because every caller is advisory.
TIMEOUT = 10

# `-c core.quotePath=false` makes git print non-ASCII paths raw instead of
# C-quoting them ("caf\303\251.py"), and `-z` makes it NUL-separate them so a
# path with a space stays one path. Splitting stdout on whitespace, as the
# previous per-caller code did, broke both — silently, since the effect is only
# that the file is never checked.
_BASE = ("-c", "core.quotePath=false")


def _run(root, *args) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *_BASE, *args],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def output(root, *args) -> str:
    """Stdout of a git command, stripped. Empty string on any failure."""
    r = _run(root, *args)
    return r.stdout.strip() if r is not None and r.returncode == 0 else ""


def _zlines(root, *args) -> list[str]:
    r = _run(root, *args)
    if r is None or r.returncode != 0:
        return []
    return [part for part in r.stdout.split("\0") if part]


def is_repo(root) -> bool:
    return bool(output(root, "rev-parse", "--show-toplevel"))


def toplevel(root) -> str:
    return output(root, "rev-parse", "--show-toplevel")


def head(root) -> str:
    return output(root, "rev-parse", "HEAD")


def source_extensions() -> tuple[str, ...]:
    """Extensions the default change discovery feeds to guard/deps. Derived from
    the language registry (every registered extension, available or not — an
    unavailable language's files still match `forbid_pattern` rules scoped to
    them), plus `.pyi` and `.rs`, which no extractor claims but which teams do
    write `forbid_pattern` rules against."""
    return tuple(dict.fromkeys(languages.all_extensions() + (".pyi", ".rs")))


def rel_to_root(root, top, files) -> list[str]:
    """Re-anchor git toplevel-relative paths to the torsor root, keeping only
    source files that live under it — so a .torsor/ in a subdirectory of the git
    repo never checks the wrong paths."""
    top_path, base = Path(top), Path(root).resolve()
    exts = source_extensions()
    out: list[str] = []
    for f in files:
        if not f.endswith(exts):
            continue
        try:
            out.append((top_path / f).relative_to(base).as_posix())
        except ValueError:
            continue  # outside the torsor root — not ours to check
    return out


def changed_source_files(root) -> list[str]:
    """Source files differing from HEAD in the working tree, plus untracked ones."""
    top = toplevel(root)
    if not top:
        return []
    changed = _zlines(root, "diff", "--name-only", "-z", "HEAD")
    # --full-name: toplevel-relative like `diff --name-only`, regardless of where
    # inside the repo the torsor root sits.
    untracked = _zlines(root, "ls-files", "--others", "--exclude-standard", "--full-name", "-z")
    return rel_to_root(root, top, changed + untracked)


def commit_source_files(root, ref: str = "HEAD") -> list[str]:
    """Source files touched by a single commit — what the post-commit hook
    remaps. `changed_source_files` diffs uncommitted state; this diffs the commit."""
    top = toplevel(root)
    if not top:
        return []
    names = _zlines(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", ref)
    return rel_to_root(root, top, names)


def config_get(root, key: str) -> str:
    """A git config value, or "" when unset — indistinguishable on purpose, since
    every caller treats "unset" and "not a repo" the same way."""
    return output(root, "config", "--get", key)


def config_set(root, key: str, value: str) -> bool:
    """Write to this clone's local config. Local, never --global: a merge driver
    is a property of one checkout, and writing it globally would silently apply
    to every repo on the machine."""
    r = _run(root, "config", "--local", key, value)
    return r is not None and r.returncode == 0


def author_slug(root) -> str:
    """A filename-safe identity for this checkout, from git's configured author.

    Used to partition journals per author so two people never append to the same
    file. Empty when git has no identity — which is not an error, it just means
    there is no partition to apply."""
    ident = config_get(root, "user.email") or config_get(root, "user.name")
    local = ident.split("@")[0].strip().lower()
    # ASCII only: str.isalnum() is true for "ć" and every other letter, and a
    # journal filename travels through git, zip archives and Windows.
    slug = "".join(ch if ch.isascii() and ch.isalnum() else "-" for ch in local).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug
