"""Golden tests for the shared renderers.

These are the strings both adapters put in front of a person or an agent, and
until render.py existed each surface built them independently and had already
drifted. Pinning them here is what makes the shared module worth having.
"""
from __future__ import annotations

from types import SimpleNamespace

from torsor_helper import render


def test_caller():
    assert render.caller({"module": "app.py", "caller": "run"}) == "app.py :: run"


def test_find_hit_covers_both_shapes():
    assert render.find_hit({"type": "file", "path": "src/a.py"}) == "src/a.py"
    assert render.find_hit(
        {"type": "symbol", "module": "src/a.py", "line": 7, "name": "f", "kind": "function"}
    ) == "src/a.py:7  f (function)"


def test_call_path_uses_the_arrow_the_caller_asks_for():
    path = [{"symbol": "a", "module": "m1"}, {"symbol": "b", "module": "m2"}]
    assert render.call_path(path) == "a (m1) -> b (m2)"
    assert render.call_path(path, arrow="→") == "a (m1) → b (m2)"


def test_violation_names_the_adr_that_declared_the_rule():
    v = SimpleNamespace(file="a.py", line=3, severity="error", message="no requests", source="ADR 0009")
    assert render.violation(v) == "a.py:3 — [error] no requests (per ADR 0009)"


def test_unknown_import():
    assert render.unknown_import({"file": "a.py", "line": 1, "name": "reqeusts"}) == \
        "a.py:1 — unknown import 'reqeusts'"


def test_staleness():
    f = SimpleNamespace(kind="dangling_link", message="a.md links to [[gone]]")
    assert render.staleness(f) == "[dangling_link] a.md links to [[gone]]"


def test_recommendation_includes_the_dismissal_key():
    r = SimpleNamespace(severity="suggest", kind="hotspot", message="x is hot",
                        action="review x", key="hotspot:x")
    assert render.recommendation(r) == "[suggest/hotspot] x is hot → review x  (key: hotspot:x)"
    assert "-> review x" in render.recommendation(r, arrow="->")


def test_recommendation_without_an_action_has_no_dangling_arrow():
    r = SimpleNamespace(severity="info", kind="thin", message="charter is a stub",
                        action="", key="thin:charter")
    assert render.recommendation(r) == "[info/thin] charter is a stub  (key: thin:charter)"


def test_command_quotes_only_when_asked():
    c = {"name": "test", "command": "pytest -q", "note": "fast"}
    assert render.command(c) == "test: pytest -q — fast"
    assert render.command(c, quote=True) == "test: `pytest -q` — fast"
    assert render.command({"name": "b", "command": "make", "note": ""}) == "b: make"


def test_recipe_shows_args_only_when_present():
    assert render.recipe({"hits": 4, "op": "recall", "args": "index"}) == "4× recall 'index'"
    assert render.recipe({"hits": 2, "op": "impact", "args": ""}) == "2× impact"


def test_recall_hit_is_the_shape_the_budget_bills():
    from torsor_helper.budget import hit_cost
    from torsor_helper.models import Tier

    hit = SimpleNamespace(title="A note", tier=Tier.ACTIVE, snippet="body text")
    rendered = render.recall_hit(hit)
    assert rendered == "### A note (ACTIVE)\nbody text"
    # the estimate must not be cheaper than the thing it is estimating
    assert hit_cost(hit.title, hit.snippet, 4) >= len(rendered) // 4
