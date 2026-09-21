import subprocess
from datetime import datetime

import pytest

FIXED_CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


@pytest.fixture
def tmp_project(tmp_path):
    """A fresh project root with a scaffolded .torsor/ and a fixed clock Store."""
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=FIXED_CLOCK)
    store.scaffold()
    return tmp_path


@pytest.fixture
def git_project(tmp_path):
    """A scaffolded project inside a real git repo with churn history: hot.py is
    complex and committed 4x; calm.py is simple and committed once."""
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    Store(TorsorPaths(tmp_path), clock=FIXED_CLOCK).scaffold()

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")
    git("config", "commit.gpgsign", "false")

    hot = tmp_path / "hot.py"
    for i in range(4):
        branches = "".join(f"    if x == {j}:\n        return {j}\n" for j in range(i + 2))
        hot.write_text(f"def f(x):\n{branches}    return -1\n")
        git("add", "hot.py")
        git("commit", "-m", f"hot {i}")

    (tmp_path / "calm.py").write_text("def g():\n    return 1\n")
    git("add", "calm.py")
    git("commit", "-m", "calm")
    return tmp_path


def fill_seeds(store):
    """Replace every seeded note with a little real content, keeping its title.

    An unfilled seed carries no information, so torsor no longer indexes it,
    bootstraps it, or hands it to get_intent (templates.is_unfilled). Tests that
    used the scaffold's seeds as convenient content were really testing "a
    project with notes in every tier"; this gives them one."""
    from torsor_helper.templates import seed_files

    body = {
        "charter.md": ("We build a message gateway that routes chat traffic to platform adapters.\n\n"
                       "## Non-negotiable principles\n- Local-first; nothing leaves the machine."),
        "system-patterns.md": "Adapters sit behind a queue; the architecture keeps the core pure.",
        "tech-context.md": "Python 3.11, SQLite for the index, no network at runtime.",
        "context.md": "Current focus: routing latency. Open question: batching strategy?",
        "progress.md": "Routing works end to end; batching is next.",
        "overview.md": "Modules are mapped here by torsor map.",
    }
    for path, seed in seed_files(store.paths).items():
        title = next((ln[2:].strip() for ln in seed.splitlines() if ln.startswith("# ")), path.stem)
        head = seed.split("\n# ", 1)[0] if seed.startswith("---") else ""
        text = body.get(path.name, f"Real content for {path.stem}: the architecture context.")
        path.write_text(f"{head}\n# {title}\n\n{text}\n" if head else f"# {title}\n\n{text}\n",
                        encoding="utf-8")
