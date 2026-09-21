"""Team memory: making two branches able to write `.torsor/` at the same time.

`.torsor/` is committed Markdown, so two people (or two agents on two branches)
working the same day both append to `memory/journal/<date>.md` and both
regenerate every note under `map/`. Git's default text merge conflicts on both,
and neither conflict is worth a human's attention: journal entries are an
append-only log, and map notes are *derived* — the merge that is always right
is "throw both away and re-run the mapper".

Two mechanisms, and they live in different places, which is the whole
difficulty:

- **`.torsor/.gitattributes`** is committed, so it travels with the repo and
  every clone gets it for free. It can only name built-in merge drivers.
  `merge=union` is built in, which is why journals are solved by the committed
  half alone.
- **A custom driver** (`map/**`) has to be registered in `.git/config`, which is
  per-clone and cannot be committed. And git does *not* warn when an attributes
  file names a driver the clone has not registered — it silently falls back to
  the normal text merge, which looks exactly like having configured nothing.
  That silence is why `status()` exists and why `doctor` reports it.

The driver never tries to merge a map note. It keeps ours, records the path,
and `torsor map --force` regenerates it from source — the only authority a
derived note has. Regenerating inside the driver was the other option; it was
rejected because the source file may itself be mid-conflict at that moment, and
the order git invokes drivers in is not specified.
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path

from torsor_helper import gitinfo

DRIVER_NAME = "torsor-map"
DRIVER_KEY = f"merge.{DRIVER_NAME}.driver"
DRIVER_NAME_KEY = f"merge.{DRIVER_NAME}.name"
DRIVER_DESCRIPTION = "keep ours and let `torsor map --force` regenerate the note"

# %A is the temp file holding our version, which the driver must leave holding
# the result; %P is the path the result will be stored at. Bare `torsor`, like
# the git hooks in hooks.py — an absolute path would go stale on reinstall, and
# a driver that cannot run exits non-zero, which git reads as "conflict". That
# is the safe direction to fail in.
DRIVER_TEMPLATE = "torsor merge driver %A %P --root {root}"


def driver_command(root) -> str:
    """git runs a merge driver from the top of the working tree, which is not
    necessarily where `.torsor/` lives — so the root is baked in, exactly as the
    git hooks in hooks.py do it."""
    return DRIVER_TEMPLATE.format(root=shlex.quote(str(Path(root).resolve())))

ATTRIBUTES: tuple[tuple[str, str], ...] = (
    # Append-only log: union keeps both sides' entries. Safe only because the
    # journal header is deterministic (store.append_journal) — with a wall-clock
    # `created:` in it, union would union the frontmatter too and leave
    # duplicate keys inside the `---` block.
    ("memory/journal/*.md", "merge=union"),
    ("map/**", f"merge={DRIVER_NAME}"),
)

_START = "# >>> torsor managed >>>"
_END = "# <<< torsor managed <<<"

_REGEN_FILE = "merge_regen.json"


def attributes_block() -> str:
    lines = [_START, *(f"{pattern} {attr}" for pattern, attr in ATTRIBUTES), _END]
    return "\n".join(lines) + "\n"


def write_attributes(paths) -> Path:
    """Write the managed block into `.torsor/.gitattributes`, keeping any line
    the user put there. Committed, unlike everything else torsor writes under
    `.torsor/` that is not a note."""
    target = paths.gitattributes
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    kept = []
    inside = False
    for line in existing.splitlines():
        if line.strip() == _START:
            inside = True
            continue
        if line.strip() == _END:
            inside = False
            continue
        if not inside:
            kept.append(line)
    body = "\n".join(line for line in kept if line.strip())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((f"{body}\n" if body else "") + attributes_block(), encoding="utf-8")
    return target


def has_attributes(paths) -> bool:
    try:
        return _START in paths.gitattributes.read_text(encoding="utf-8")
    except OSError:
        return False


# ---- the per-clone half ----

def driver_registered(root) -> bool:
    return bool(gitinfo.config_get(root, DRIVER_KEY))


def register_driver(root) -> bool:
    """Register the map driver in this clone's `.git/config`. Returns False when
    `root` is not a git repo — nothing to register into."""
    if not gitinfo.is_repo(root):
        return False
    gitinfo.config_set(root, DRIVER_KEY, driver_command(root))
    gitinfo.config_set(root, DRIVER_NAME_KEY, DRIVER_DESCRIPTION)
    return True


def status(root, paths) -> dict:
    """Everything a caller needs to say which half is missing."""
    repo = gitinfo.is_repo(root)
    return {
        "git_repo": repo,
        "attributes": has_attributes(paths),
        "attributes_path": str(paths.gitattributes),
        "driver_registered": repo and driver_registered(root),
        "driver_command": gitinfo.config_get(root, DRIVER_KEY) if repo else "",
        "pending_regeneration": pending_regeneration(paths),
    }


# ---- the driver itself ----

def _base_relative(path: str) -> str:
    """git hands the driver a repo-root-relative path; everything else in torsor
    talks in paths relative to `.torsor/`."""
    posix = Path(path).as_posix()
    if posix.startswith("./"):
        posix = posix[2:]
    # str.lstrip("./") would strip the leading dot of ".torsor" as well — it
    # takes a character set, not a prefix.
    marker = ".torsor/"
    return posix[posix.index(marker) + len(marker):] if marker in posix else posix


def resolve_map_note(paths, ours: Path, merged_path: str) -> int:
    """Resolve a `map/**` merge by keeping ours and queueing a regeneration.

    `ours` already holds our version — git copies whatever the driver leaves
    there into the worktree — so "keep ours" is literally doing nothing to it.
    The return value is the driver's exit status: 0 means resolved.
    """
    rel = _base_relative(merged_path)
    pending = set(pending_regeneration(paths))
    pending.add(rel)
    _write_pending(paths, sorted(pending))
    return 0 if Path(ours).exists() else 1


def pending_regeneration(paths) -> list[str]:
    """Map notes a merge resolved by taking ours, awaiting `torsor map --force`."""
    from torsor_helper.store import state_file

    try:
        data = json.loads(state_file(paths, _REGEN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(str(p) for p in data) if isinstance(data, list) else []


def _write_pending(paths, items: list[str]) -> None:
    from torsor_helper.store import state_file

    target = state_file(paths, _REGEN_FILE)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(items, indent=2), encoding="utf-8")
    except OSError:
        pass  # a queue we cannot write just means the user remaps by hand


def clear_pending(paths) -> None:
    """Called after a full remap, which regenerates every map note anyway."""
    from torsor_helper.store import state_file

    try:
        state_file(paths, _REGEN_FILE).unlink(missing_ok=True)
    except OSError:
        pass
