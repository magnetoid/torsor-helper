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
