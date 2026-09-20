"""A guard rule's `scope` must mean what its author wrote.

fnmatch treats `*` as matching `/` and gives `**` no special meaning, so
`src/pkg/*.py` silently governed `src/pkg/sub/deep.py` too, and `src/**/*.ts`
— the form the multi-language spec prescribes — matched nothing under `src/`
directly. Both failures are invisible: a scope that matches nothing reports
nothing, exactly like a rule that passes.
"""
from __future__ import annotations

import pytest

from torsor_helper.guard import scope_matches


@pytest.mark.parametrize("scope, path, expected", [
    # A single * stays inside one path segment.
    ("src/pkg/*.py", "src/pkg/mod.py", True),
    ("src/pkg/*.py", "src/pkg/sub/deep.py", False),
    ("src/pkg/*.py", "src/other/mod.py", False),

    # ** spans directories, including zero of them.
    ("src/**/*.ts", "src/index.ts", True),
    ("src/**/*.ts", "src/a/b/c.ts", True),
    ("src/**/*.ts", "lib/a.ts", False),
    ("src/**", "src/a.py", True),
    ("src/**", "src/a/b/c.py", True),
    ("src/**", "tests/a.py", False),

    # A bare pattern with no "/" matches at any depth, as .gitignore does —
    # `scope: "*.py"` has always meant "Python files", and rules in the wild
    # rely on it.
    ("*.py", "a.py", True),
    ("*.py", "src/pkg/a.py", True),
    ("*.ts", "src/a.py", False),

    # Character classes keep working; this repo's ADR 0013 uses them.
    ("src/torsor_helper/[!l]*.py", "src/torsor_helper/cli.py", True),
    ("src/torsor_helper/[!l]*.py", "src/torsor_helper/languages.py", False),
    ("src/torsor_helper/languages/[!t]*.py", "src/torsor_helper/languages/go.py", True),
    ("src/torsor_helper/languages/[!t]*.py", "src/torsor_helper/languages/treesitter.py", False),

    # An exact path is an exact path.
    ("src/torsor_helper/guard.py", "src/torsor_helper/guard.py", True),
    ("src/torsor_helper/guard.py", "src/torsor_helper/guard_extra.py", False),
])
def test_scope_semantics(scope, path, expected):
    assert scope_matches(path, scope) is expected


def test_this_repos_own_adr_scopes_still_cover_what_they_mean_to():
    # ADR 0002 must reach every core module, including the subpackages.
    assert scope_matches("src/torsor_helper/cli.py", "src/torsor_helper/**/*.py")
    assert scope_matches("src/torsor_helper/coach/hubs.py", "src/torsor_helper/**/*.py")
    assert scope_matches("src/torsor_helper/operations/gate.py", "src/torsor_helper/**/*.py")
    # ADR 0014 governs the operations package and nothing above it.
    assert scope_matches("src/torsor_helper/operations/memory.py", "src/torsor_helper/operations/*.py")
    assert not scope_matches("src/torsor_helper/cli.py", "src/torsor_helper/operations/*.py")
