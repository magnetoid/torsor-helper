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
