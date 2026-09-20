"""The operations package must not depend on its own façade.

While `operations/__init__.py` runs, the module object exists but is only
partly populated. A submodule that imports the façade during that window gets a
half-built module — and whether that raises depends on import order, so it can
pass under pytest (which has already imported everything) and fail for a user.
ADR 0014 forbids it; this checks it in a cold interpreter, where it would bite.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "src" / "torsor_helper" / "operations"
SUBMODULES = sorted(p.stem for p in PKG.glob("*.py") if p.stem != "__init__")


def test_there_are_submodules_to_check():
    assert len(SUBMODULES) >= 8


@pytest.mark.parametrize("name", SUBMODULES)
def test_each_submodule_imports_in_a_cold_interpreter(name):
    proc = subprocess.run(
        [sys.executable, "-c", f"import torsor_helper.operations.{name}"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


def test_the_facade_still_exposes_the_whole_surface():
    from torsor_helper import operations as ops

    # A sample across every concern — the adapters and 34 test modules reach
    # these through the façade and must keep doing so.
    for name in ("bootstrap_session", "recall", "remember", "map_repo", "impact", "connect",
                 "verify", "check_drift", "recommend", "clean", "consolidate", "install_hooks",
                 "record_decision", "agent_rules", "project_primer", "list_commands",
                 "auto_handoff", "pre_edit", "session_start_context"):
        assert callable(getattr(ops, name)), name


def test_no_submodule_imports_the_facade():
    # The guard enforces this too (ADR 0014); this fails with a clearer message.
    offenders = [
        p.name for p in PKG.glob("*.py")
        if p.stem != "__init__"
        and ("from torsor_helper.operations import" in p.read_text()
             or "\nfrom . import " in p.read_text())
    ]
    assert offenders == []
