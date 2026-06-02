from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_bootstrap_includes_all_tiers(tmp_path):
    store = _store(tmp_path)
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "## Charter" in out
    assert "## System Patterns" in out
    assert "## Active Context" in out
    assert "## Progress" in out


def test_bootstrap_respects_total_budget(tmp_path):
    store = _store(tmp_path)
    cfg = TorsorConfig()
    cfg.budgets.bootstrap_tokens = 40  # tiny
    out = ops.bootstrap_session(store, cfg)
    assert len(out) < 1200


def test_remember_appends_journal_and_recall_finds_it(tmp_path):
    store = _store(tmp_path)
    path = ops.remember(store, "We chose SQLite for the index", kind="decision", links=["tech-context"])
    assert path.endswith("2026-06-01.md")
    res = ops.recall(store, TorsorConfig(), "SQLite")
    assert any("SQLite" in h.snippet for h in res.hits)


def test_update_active_rewrites_context_and_progress(tmp_path):
    store = _store(tmp_path)
    ops.update_active(store, focus="Build Phase 1", progress="Tasks 1-9 done", open_questions="None")
    ctx = store.paths.active_context.read_text()
    prog = store.paths.progress.read_text()
    assert "Build Phase 1" in ctx
    assert "None" in ctx
    assert "Tasks 1-9 done" in prog


def test_record_handoff_is_recallable_next_session(tmp_path):
    store = _store(tmp_path)
    ops.record_handoff(
        store,
        summary="Finished store + recall",
        decisions="Markdown is source of truth",
        open_questions="vector backend?",
        next_steps="start Phase 2 indexer",
    )
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "Finished store + recall" in out


def test_recent_journal_spans_multiple_days(tmp_path):
    # Regression: a fresh/sparse newest day must not hide the prior day's memory.
    store = _store(tmp_path)
    store.paths.journal_dir.joinpath("2025-01-01.md").write_text(
        "---\ntype: journal\n---\n\n# Journal 2025-01-01\n\n## 09:00 - decision\n\nchose alpha approach\n",
        encoding="utf-8",
    )
    store.paths.journal_dir.joinpath("2026-06-02.md").write_text(
        "---\ntype: journal\n---\n\n# Journal 2026-06-02\n\n## 09:00 - note\n\nbeta update\n",
        encoding="utf-8",
    )
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "beta update" in out   # newest day
    assert "alpha approach" in out  # older day still surfaced within budget


def test_bootstrap_weaves_recommendations_digest(tmp_path):
    store = _store(tmp_path)  # fresh scaffold -> thin recs present
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "## Recommendations" in out
    assert "seed template" in out.lower()  # the thin hygiene nudge
