"""Every context-returning path must honour a token budget.

CLAUDE.md states the invariant ("budget.py — every context-returning path is
token-budgeted"); these tests are what makes it true. The bar is deliberately
hard: an *honest* cap (one that tells the agent what it did not show) costs a
few tokens and saves a blind re-query, so each cap is asserted together with the
true total it reports.
"""
from __future__ import annotations

from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.budget import cap_items, estimate_tokens
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 9, 20, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def _fat(store, words=4000):
    """Fill every seeded note past any plausible budget."""
    filler = " ".join(f"word{i}" for i in range(words))
    for path in (store.paths.charter, store.paths.system_patterns, store.paths.tech_context,
                 store.paths.active_context, store.paths.progress):
        path.write_text(f"---\ntype: note\n---\n\n# Big\n\n{filler}\n", encoding="utf-8")
    store.paths.journal_dir.mkdir(parents=True, exist_ok=True)
    (store.paths.journal_dir / "2026-09-19.md").write_text(
        f"---\ntype: journal\n---\n\n# Journal\n\n## 09:00 - note\n\n{filler}\n", encoding="utf-8"
    )


def _tokens(text, config):
    return estimate_tokens(text, config.budgets.chars_per_token)


# --- budget.cap_items -------------------------------------------------------

def test_cap_items_keeps_everything_when_it_fits():
    kept, tail = cap_items(["a", "b"], 5)
    assert kept == ["a", "b"]
    assert tail == ""


def test_cap_items_reports_how_many_it_dropped():
    kept, tail = cap_items(list(range(10)), 3)
    assert kept == [0, 1, 2]
    assert "7 more" in tail


def test_cap_items_tail_carries_the_caller_hint():
    _, tail = cap_items(list(range(10)), 3, more="raise limit")
    assert "raise limit" in tail


def test_cap_items_treats_a_non_positive_cap_as_no_cap():
    kept, tail = cap_items([1, 2, 3], 0)
    assert kept == [1, 2, 3] and tail == ""


# --- the auto-injected digest (the most expensive path: every start + compact)

def test_session_start_context_never_exceeds_its_budget(tmp_path):
    store = _store(tmp_path)
    _fat(store)
    config = TorsorConfig()

    text = ops.session_start_context(store, config, how="startup")

    assert text is not None
    assert _tokens(text, config) <= config.budgets.session_start_tokens


def test_bootstrap_session_never_exceeds_its_budget(tmp_path):
    store = _store(tmp_path)
    _fat(store)
    config = TorsorConfig()

    assert _tokens(ops.bootstrap_session(store, config), config) <= config.budgets.bootstrap_tokens


def test_bootstrap_coach_digest_is_inside_the_budget_not_appended_after_it(tmp_path):
    # Regression: the Coach section used to be appended *after* every allocation
    # was spent, so the 500-token SessionStart digest overran on every session.
    store = _store(tmp_path)
    _fat(store)
    config = TorsorConfig()
    config.budgets.bootstrap_tokens = 300

    out = ops.bootstrap_session(store, config)

    assert _tokens(out, config) <= 300


# --- get_intent -------------------------------------------------------------

def test_get_intent_respects_its_own_budget(tmp_path):
    store = _store(tmp_path)
    _fat(store)
    config = TorsorConfig()

    assert _tokens(ops.get_intent(store, config), config) <= config.budgets.intent_tokens


def test_get_intent_caps_the_decision_list_and_says_how_many_it_hid(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    for i in range(config.budgets.max_items + 15):
        (store.paths.decisions_dir / f"{i:04d}-decision-{i}.md").write_text(
            f"---\ntype: decision\n---\n\n# ADR {i}: choice number {i}\n\nbody\n", encoding="utf-8"
        )

    total = len(list(store.paths.decisions_dir.glob("*.md")))  # + the seeded ADR 0001

    out = ops.get_intent(store, config)

    decisions = out.split("## Decisions", 1)[1]
    assert decisions.count("\n- ") <= config.budgets.max_items
    assert f"+{total - config.budgets.max_items} more" in decisions


# --- impact (the single most expensive tool call measured on this repo) ------

def test_impact_caps_callers_but_still_reports_the_true_total(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "dates.py").write_text("def fmt(d):\n    return d\n")
    callers = 40
    for i in range(callers):
        (tmp_path / f"caller{i}.py").write_text(
            f"from pkg.dates import fmt\n\ndef run{i}():\n    return fmt({i})\n"
        )
    config = TorsorConfig()
    ops.map_repo(store, config)

    res = ops.impact(store, config, "fmt", limit=10)

    assert res["count"] == callers          # the blast radius is the valuable signal
    assert len(res["callers"]) == 10        # ...but we do not pay to print it all
    assert res["truncated"] == callers - 10


def test_impact_limit_defaults_to_the_configured_cap(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "dates.py").write_text("def fmt(d):\n    return d\n")
    config = TorsorConfig()
    config.budgets.max_items = 5
    for i in range(12):
        (tmp_path / f"caller{i}.py").write_text(
            f"from pkg.dates import fmt\n\ndef run{i}():\n    return fmt({i})\n"
        )
    ops.map_repo(store, config)

    res = ops.impact(store, config, "fmt")

    assert len(res["callers"]) == 5
    assert res["count"] == 12


# --- list_practices ---------------------------------------------------------

def test_list_practices_respects_its_budget(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.ts").write_text("export const x = 1\n")
    (tmp_path / "c.go").write_text("package main\n")
    config = TorsorConfig()

    out = ops.list_practices(store, config, None)

    assert _tokens(out, config) <= config.budgets.practices_tokens


# --- verify -----------------------------------------------------------------

def test_verify_caps_reasons_per_check_but_keeps_the_true_count(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(
        store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "*.py", "severity": "error"}],
    )
    config = TorsorConfig()
    config.budgets.max_items = 3
    files = []
    for i in range(9):
        (tmp_path / f"bad{i}.py").write_text("import requests\n")
        files.append(f"bad{i}.py")

    v = ops.verify(store, config, files)

    guard = next(c for c in v["checks"] if c["name"] == "guard")
    assert guard["count"] == 9           # the honest total a gate should act on
    assert len(guard["reasons"]) <= 3    # but not nine lines of prose


# --- recall (the most-called tool) ------------------------------------------

def _render_recall(result):
    """Exactly how server.py renders a RecallResult into the agent's context."""
    return "\n\n".join(f"### {h.title} ({h.tier.name})\n{h.snippet}" for h in result.hits)


def test_recall_budget_covers_what_actually_lands_in_context(tmp_path):
    # Regression: the budget accounted only the snippet, while every hit also
    # carries a title and a heading — so a wide recall overran by ~28%.
    store = _store(tmp_path)
    config = TorsorConfig()
    config.budgets.recall_tokens = 400
    for i in range(40):
        (store.paths.memory_dir / f"note-{i}.md").write_text(
            f"---\ntype: note\n---\n\n# A deliberately long note title number {i} about widget indexing\n\n"
            + " ".join(f"widget{j}" for j in range(60)) + "\n",
            encoding="utf-8",
        )

    result = ops.recall(store, config, "widget", limit=40)

    assert _tokens(_render_recall(result), config) <= config.budgets.recall_tokens


def test_recall_reported_total_matches_what_it_charged(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    for i in range(5):
        (store.paths.memory_dir / f"n{i}.md").write_text(
            f"---\ntype: note\n---\n\n# Note {i}\n\nwidget content {i}\n", encoding="utf-8"
        )

    result = ops.recall(store, config, "widget", limit=5)

    assert result.total_tokens >= _tokens(_render_recall(result), config) - 2
