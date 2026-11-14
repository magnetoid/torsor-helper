"""Build the torsor arm's `.torsor/` for a janus checkout from real material only.

Everything torsor gets to know comes from the repository itself, so the arm
is not fed the answers:

- charter and active context: copied from the janus checkout's own `.torsor/`
  if it has one (written during real use), else left as the init seed
- journal: one observation per recent non-merge commit, subject + body, the
  way the post-commit hook records them
- ADRs with rules: three decisions transcribed from AGENTS.md "Known Pitfalls",
  with the machine-checkable rule each one implies. The prose already exists
  in the repo for both arms; the rule is what only torsor can enforce.
- code map: `torsor map`
- hooks and MCP config: `torsor hooks install --no-git`, `torsor init --write`

Usage: uv run python tests/bench/agent_eval/seed_torsor.py <janus-checkout> [--commits 20]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ADRS = [
    dict(
        title="Resolve the Janus home through get_janus_home(), never a literal ~/.janus",
        context=(
            "Profiles give each instance its own JANUS_HOME. A hardcoded `Path.home() / '.janus'` "
            "or `~/.janus` string works on the default profile and silently reads the wrong "
            "directory on every other one; PR #3575 fixed five such bugs (AGENTS.md, Known Pitfalls)."
        ),
        decision=(
            "Code paths call `get_janus_home()` from janus_constants; user-facing text calls "
            "`display_janus_home()`. Tests redirect JANUS_HOME through the autouse fixture."
        ),
        consequences="Existing literals are baselined; the guard reports new ones on edit.",
        rules=[
            dict(kind="forbid_pattern", target=r"Path\.home\(\)\s*/\s*[\"']\.janus", scope="**/*.py",
                 exclude="tests/**", message="use get_janus_home() — a literal ~/.janus breaks profiles"),
            dict(kind="forbid_pattern", target=r"[\"']~/\.janus", scope="**/*.py",
                 exclude="tests/**", message="use display_janus_home() for user-facing paths"),
        ],
    ),
    dict(
        title="New interactive menus use the curses UI, not simple_term_menu",
        context=(
            "simple_term_menu has ghost-duplication rendering bugs in tmux and iTerm2 with arrow "
            "keys. The remaining call sites in janus_cli/main.py and janus_cli/auth.py are legacy "
            "fallbacks (AGENTS.md, Known Pitfalls)."
        ),
        decision="New menus go through janus_cli/curses_ui.py; janus_cli/tools_config.py is the pattern.",
        consequences="Importing simple_term_menu anywhere new is a guard finding.",
        rules=[
            dict(kind="forbid_import", target="simple_term_menu", scope="**/*.py",
                 exclude="janus_cli/main.py", message="new menus use janus_cli/curses_ui.py"),
        ],
    ),
    dict(
        title="Spinner and display code never emits the ANSI erase-to-EOL sequence",
        context=(
            "`\\033[K` leaks as literal `?[K` text under prompt_toolkit's patch_stdout "
            "(AGENTS.md, Known Pitfalls)."
        ),
        decision="Repaint-in-place lines are space-padded to the previous width instead.",
        consequences="Any `\\033[K` or `\\x1b[K` in a Python source is a guard finding.",
        rules=[
            dict(kind="forbid_pattern", target=r"\\(033|x1b|e)\[K", scope="**/*.py",
                 message="pad with spaces; \\033[K leaks under patch_stdout"),
        ],
    ),
]


def sh(*args: str, cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(list(args), cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode:
        sys.exit(f"$ {' '.join(args)}\n{proc.stdout}{proc.stderr}")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkout", type=Path)
    ap.add_argument("--source-torsor", type=Path, default=None,
                    help="a .torsor/ from real use whose charter and active context to carry over")
    ap.add_argument("--commits", type=int, default=20)
    args = ap.parse_args()
    root: Path = args.checkout.resolve()
    torsor_dir = root / ".torsor"
    if torsor_dir.exists():
        shutil.rmtree(torsor_dir)

    sh("torsor", "init", "--write", cwd=root)
    if args.source_torsor:
        for rel in ("charter.md", "active/context.md", "active/progress.md"):
            src = args.source_torsor / rel
            if src.exists():
                (torsor_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, torsor_dir / rel)

    log = sh("git", "log", "--no-merges", f"-{args.commits}", "--format=%h%x1f%s%x1f%b%x1e", cwd=root)
    for entry in filter(None, log.split("\x1e")):
        sha, subject, body = (entry.strip("\n").split("\x1f") + ["", ""])[:3]
        text = f"commit {sha}: {subject}"
        if body.strip():
            text += "\n" + body.strip()
        sh("torsor", "remember", text, "--kind", "observation", cwd=root)

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
    from torsor_helper import operations as ops
    from torsor_helper.config import load_config
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    paths = TorsorPaths(root)
    store = Store.for_config(paths, load_config(paths))
    for adr in ADRS:
        ops.record_decision(store, adr["title"], adr["context"], adr["decision"],
                            adr["consequences"], rules=adr["rules"])

    sh("torsor", "map", "--force", cwd=root)
    sh("torsor", "index", cwd=root)
    sh("torsor", "hooks", "install", "--no-git", cwd=root)
    print(sh("torsor", "doctor", cwd=root, check=False))
    print(sh("torsor", "guard", "--strict", "janus_cli/main.py", "janus_constants.py", cwd=root, check=False))


if __name__ == "__main__":
    main()
