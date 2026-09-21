"""Hotspots without parsing every file in the repo.

On a real 3 200-file project `find_hotspots` spent ~20 s computing complexity
for every file git had ever touched, to report three. Complexity is newline
count plus branch nodes, and every branch node needs at least one branch
*token* in the source — so counting those tokens is an upper bound, and the top
k can be found exactly while parsing only the files that could still make it.

The bound being a true upper bound is the whole correctness argument, so it is
checked against every source file in this repo, not only against snippets.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from torsor_helper import languages
from torsor_helper.coach import hotspots

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name, text", [
    ("a.py", "if a and b or c:\n    pass\nelif d:\n    for x in y:\n        while z:\n            try:\n"
             "                pass\n            except E:\n                pass\n"),
    ("a.py", "x = [i for i in y if i and j]\nz = a if b else c\n"),
    ("a.js", "if (a && b || c) { for (;;) {} } while (x) {} do {} while (y);\n"
             "switch (v) { case 1: break; }\ntry {} catch (e) {}\nconst t = a ? b : c ?? d;\n"),
    ("a.ts", "function f(x: number): string { return x > 0 ? 'p' : x < 0 ? 'n' : 'z'; }\n"),
    ("a.go", "package a\nfunc f() {\n  if a && b || c {}\n  for {}\n  switch x { case 1: }\n"
             "  select { case <-ch: }\n}\n"),
])
def test_the_bound_is_never_below_the_real_complexity(tmp_path, name, text):
    # spec_for is None for a language whose extra is not installed — and then
    # complexity_bound is infinite, so nothing is pruned (tested below).
    spec = languages.spec_for(Path(name))
    if spec is None or not languages.is_available(spec.name):
        pytest.skip("language not available")
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    assert hotspots.complexity_bound(path, text) >= languages.complexity(path)


def test_the_bound_holds_on_every_real_file_in_this_repo():
    """Snippets prove the idea; this proves it on code nobody wrote to pass."""
    checked = 0
    for rel in subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                              text=True, check=True).stdout.split():
        path = REPO / rel
        spec = languages.spec_for(path)
        if spec is None or not languages.is_available(spec.name):
            continue
        text = path.read_text(encoding="utf-8-sig")
        assert hotspots.complexity_bound(path, text) >= languages.complexity(path), rel
        checked += 1
    assert checked > 100


def test_an_unknown_language_is_never_pruned(tmp_path):
    """The bound is only valid for languages whose branch tokens it knows."""
    path = tmp_path / "a.rs"
    assert hotspots.complexity_bound(path, "fn f() {}") == float("inf")


def test_an_unavailable_language_is_never_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(languages, "spec_for", lambda path: None)
    assert hotspots.complexity_bound(tmp_path / "a.ts", "if (a) {}") == float("inf")


def _repo_with_history(tmp_path, files):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@e.x")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    for name, (body, commits) in files.items():
        for i in range(commits):
            (tmp_path / name).write_text(body + f"\n# rev {i}\n", encoding="utf-8")
            git("add", name)
            git("commit", "-qm", f"{name} {i}")


def _branchy(n):
    return "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(n))


def test_pruned_hotspots_equal_brute_force(tmp_path):
    """Exact, not approximate: the same files in the same order as scoring
    every one. Includes a very complex file with little churn and a trivial file
    with a lot, which is where a churn-only shortcut would get it wrong."""
    _repo_with_history(tmp_path, {
        "hot.py": (_branchy(40), 6),
        "huge_rare.py": (_branchy(400), 1),
        "busy_trivial.py": ("x = 1\n", 12),
        "mid.py": (_branchy(15), 4),
        "tie_a.py": (_branchy(10), 3),
        "tie_b.py": (_branchy(10), 3),
        "calm.py": (_branchy(2), 1),
    })
    for limit in (1, 2, 3, 5, 10):
        fast = hotspots.find_hotspots(tmp_path, limit=limit)
        slow = hotspots.find_hotspots(tmp_path, limit=limit, prune=False)
        assert [r.key for r in fast] == [r.key for r in slow], limit
        assert [r.score for r in fast] == [r.score for r in slow], limit


def test_pruning_actually_skips_files(tmp_path, monkeypatch):
    _repo_with_history(tmp_path, {f"f{i}.py": (_branchy(2), 1) for i in range(30)}
                       | {"hot.py": (_branchy(80), 10)})
    computed = []
    real = hotspots._complexity

    def spy(path):
        computed.append(path.name)
        return real(path)

    monkeypatch.setattr(hotspots, "_complexity", spy)
    hotspots.find_hotspots(tmp_path, limit=1)
    assert len(computed) < 31, f"parsed {len(computed)} of 31 to report one"


def test_churn_asks_for_the_extension_list_once(tmp_path, monkeypatch):
    """It was called once per line of `git log` output — every line re-checked
    that each language's modules import."""
    _repo_with_history(tmp_path, {"a.py": ("x = 1\n", 5)})
    calls = []
    real = languages.source_extensions
    monkeypatch.setattr(languages, "source_extensions", lambda: calls.append(1) or real())
    hotspots._churn(tmp_path, 365)
    assert len(calls) == 1


# ---- "N source modules not in the map", right after mapping ----
#
# The same real project reported 265 uncharted modules immediately after a full
# `torsor map`. Every one had been scanned; they just define no symbols — empty
# and re-export __init__.py files, `__main__.py`, a `main.tsx` entry point, a
# `vite.config.ts` that only does `export default`. The check subtracted
# "modules that have symbols" from "source files", so on any real repo it said
# "run `torsor map`" forever, and running it changed nothing.

def _mapped(tmp_path):
    from torsor_helper import operations as ops
    from torsor_helper.config import TorsorConfig
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "__main__.py").write_text("from pkg.core import run\nrun()\n", encoding="utf-8")
    (tmp_path / "pkg" / "core.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    ops.map_repo(store, TorsorConfig())
    return store


def _uncharted(store):
    """Through ops.recommend, the way both adapters reach it: assemble() on its
    own gets no index connection, so it has no map to consult at all."""
    from torsor_helper import operations as ops
    from torsor_helper.config import TorsorConfig

    return [r for r in ops.recommend(store, TorsorConfig(), limit=50) if r.kind == "uncharted"]


def test_a_freshly_mapped_repo_has_nothing_uncharted(tmp_path):
    assert _uncharted(_mapped(tmp_path)) == []


def test_a_change_after_mapping_says_the_map_is_out_of_date(tmp_path):
    store = _mapped(tmp_path)
    (tmp_path / "pkg" / "new.py").write_text("def added():\n    return 2\n", encoding="utf-8")
    recs = _uncharted(store)
    assert len(recs) == 1
    assert "out of date" in recs[0].message and "265" not in recs[0].message


def test_no_map_at_all_still_says_so(tmp_path):
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    recs = _uncharted(store)
    assert len(recs) == 1 and "torsor map" in recs[0].message
