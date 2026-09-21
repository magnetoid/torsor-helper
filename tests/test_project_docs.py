"""Project documentation that already exists, read in place.

On a real project a fresh `torsor init` left memory empty — seed templates and
2 952 map notes — while the project's actual knowledge sat in README.md,
CONTRIBUTING.md and docs/, none of which torsor read. Copying those files into
.torsor/ would duplicate them in git and go stale the moment anyone edited the
original, so they are indexed where they are: read-only, re-read when they
change, never written.

CLAUDE.md and AGENTS.md are deliberately not in the defaults. Every client
already loads its own instructions file into context, so recalling it again
spends tokens on text the agent is already holding.
"""
from __future__ import annotations

import os

import pytest

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.models import TIER_WEIGHTS, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

DEFAULT = TorsorConfig().memory.sources


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _store(tmp_path, sources=DEFAULT):
    store = Store(TorsorPaths(tmp_path), doc_sources=list(sources))
    store.scaffold()
    return store


def _rel(store, paths):
    return sorted(p.relative_to(store.paths.root).as_posix() for p in paths)


# ---- which files ----

def test_the_defaults_cover_conventional_docs_but_not_agent_instructions():
    assert "README.md" in DEFAULT
    assert "docs/**/*.md" in DEFAULT
    assert not any("CLAUDE" in p or "AGENTS" in p for p in DEFAULT)


def test_patterns_are_anchored_at_the_root(tmp_path):
    """`README.md` means the project's README, not every README at any depth —
    the .gitignore rule the guard uses would have pulled in one per plugin."""
    store = _store(tmp_path)
    _write(tmp_path, "README.md", "# Top\n")
    _write(tmp_path, "plugins/x/README.md", "# Nested\n")
    _write(tmp_path, "docs/a.md", "# A\n")
    _write(tmp_path, "docs/deep/b.md", "# B\n")
    _write(tmp_path, "docs/notes.txt", "not markdown\n")
    assert _rel(store, store.iter_doc_paths()) == ["README.md", "docs/a.md", "docs/deep/b.md"]


def test_torsor_s_own_notes_are_never_doc_sources(tmp_path):
    """They are indexed already, as the tier they belong to."""
    store = _store(tmp_path, ["**/*.md"])
    _write(tmp_path, "notes/x.md", "# X\n")
    assert _rel(store, store.iter_doc_paths()) == ["notes/x.md"]


def test_ignored_directories_are_pruned(tmp_path):
    store = _store(tmp_path, ["**/*.md"])
    _write(tmp_path, "node_modules/pkg/README.md", "# dep\n")
    _write(tmp_path, ".git/x.md", "# git\n")
    _write(tmp_path, "real.md", "# real\n")
    assert _rel(store, store.iter_doc_paths()) == ["real.md"]


@pytest.mark.parametrize("pattern", ["../outside.md", "/etc/*.md", "docs/../../outside.md"])
def test_a_pattern_cannot_reach_outside_the_project(tmp_path, pattern):
    """torsor.toml travels in git, so a pattern is untrusted input."""
    inner = tmp_path / "proj"
    inner.mkdir()
    _write(tmp_path, "outside.md", "# secret\n")
    store = _store(inner, [pattern])
    assert list(store.iter_doc_paths()) == []


def test_a_symlink_out_of_the_project_is_not_followed(tmp_path):
    outside = tmp_path / "elsewhere"
    _write(outside, "secret.md", "# secret\n")
    proj = tmp_path / "proj"
    store = _store(proj)
    (proj / "docs").mkdir()
    os.symlink(outside / "secret.md", proj / "docs" / "link.md")
    assert list(store.iter_doc_paths()) == []


def test_no_sources_means_no_docs(tmp_path):
    """A Store built without config — every existing test — reads nothing extra."""
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    _write(tmp_path, "README.md", "# Top\n")
    assert list(store.iter_doc_paths()) == []


# ---- recall ----

def test_recall_finds_what_the_project_already_wrote_down(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/gateway.md",
           "# Message routing\n\nThe gateway routes each inbound message to a platform adapter.\n")
    result = ops.recall(store, TorsorConfig(), "gateway routes inbound message")
    top = result.hits[0]
    assert top.title == "Message routing"
    assert top.tier is Tier.DOCS


def test_docs_can_be_filtered_by_type(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/gateway.md", "# Routing\n\nThe gateway routes messages.\n")
    store.append_journal("the gateway routes messages oddly on Mondays", kind="learning", links=[])
    hits = ops.recall(store, TorsorConfig(), "gateway routes messages", type_="doc").hits
    assert [h.title for h in hits] == ["Routing"]


def test_a_doc_that_declares_its_own_type_keeps_it(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/adr/0001.md", "---\ntype: decision\n---\n\n# Use queues\n\nWe use queues.\n")
    hits = ops.recall(store, TorsorConfig(), "queues", type_="decision").hits
    assert [h.title for h in hits] == ["Use queues"]


def test_an_edited_doc_is_reindexed_and_a_deleted_one_disappears(tmp_path):
    store = _store(tmp_path)
    doc = _write(tmp_path, "docs/a.md", "# A\n\nalpha content\n")
    config = TorsorConfig()
    assert ops.recall(store, config, "alpha").hits
    doc.write_text("# A\n\nbeta content now\n", encoding="utf-8")
    assert ops.recall(store, config, "beta").hits
    doc.unlink()
    assert not [h for h in ops.recall(store, config, "beta").hits if h.tier is Tier.DOCS]


def test_removing_a_pattern_drops_its_docs_from_the_index(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/a.md", "# A\n\nzebra content\n")
    config = TorsorConfig()
    assert ops.recall(store, config, "zebra").hits
    narrowed = Store(store.paths, doc_sources=["README.md"])
    assert not [h for h in ops.recall(narrowed, config, "zebra").hits if h.tier is Tier.DOCS]


def test_the_keyword_fallback_reads_docs_too(tmp_path):
    """No index (auto_index off, nothing built): recall reads Markdown directly,
    and must see the same notes the indexed path does."""
    store = _store(tmp_path)
    _write(tmp_path, "docs/a.md", "# Queues\n\nwe use durable queues\n")
    config = TorsorConfig()
    config.index.auto_index = False
    hits = ops.recall(store, config, "durable queues").hits
    assert [h.title for h in hits] == ["Queues"]


def test_impact_reports_docs_that_mention_the_symbol(tmp_path):
    """The memory-to-symbol link (ADR 0016) extends to the project's own docs."""
    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def route_message():\n    return 1\n", encoding="utf-8")
    _write(tmp_path, "docs/gateway.md", "# Routing\n\n`route_message` picks the adapter.\n")
    ops.map_repo(store, TorsorConfig())
    titles = [m["title"] for m in ops.impact(store, TorsorConfig(), "route_message")["mentions"]]
    assert "Routing" in titles


# ---- never written ----

def test_torsor_never_writes_a_project_doc(tmp_path):
    """The one property that makes reading them in place safe. Everything that
    writes Markdown is exercised here: reindex, recall's access bumps, staleness
    marking (which rewrites frontmatter), clean, consolidate, and a map."""
    store = _store(tmp_path)
    doc = _write(tmp_path, "docs/a.md", "# A\n\nSee [[nonexistent]] and `src/missing.py`.\n")
    readme = _write(tmp_path, "README.md", "# Project\n")
    before = {p: p.read_bytes() for p in (doc, readme)}
    stat_before = {p: p.stat().st_mtime_ns for p in (doc, readme)}
    config = TorsorConfig()

    ops.recall(store, config, "project")
    ops.check_staleness(store, config, mark=True)
    ops.clean(store, config, apply=True)
    ops.consolidate(store, config)
    ops.map_repo(store, config)
    ops.recall(store, config, "nonexistent")

    for path, data in before.items():
        assert path.read_bytes() == data, path
        assert path.stat().st_mtime_ns == stat_before[path], path


def test_clean_never_lists_a_project_doc(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/a.md", "# A\n")
    ops.recall(store, TorsorConfig(), "a")
    plan = ops.clean(store, TorsorConfig())
    listed = str(plan)
    assert "docs/a.md" not in listed


# ---- tier ----

def test_docs_rank_between_curated_intent_and_derived_notes():
    """Authored by the project, so above the map (derived) and working notes;
    not curated as intent, so below charter and architecture."""
    assert TIER_WEIGHTS[Tier.MAP] < TIER_WEIGHTS[Tier.DOCS] < TIER_WEIGHTS[Tier.ARCHITECTURE]
    assert TIER_WEIGHTS[Tier.ACTIVE] < TIER_WEIGHTS[Tier.DOCS]


def test_importance_floors_accept_the_new_tier(tmp_path):
    paths = TorsorPaths(tmp_path)
    paths.base.mkdir()
    paths.config_file.write_text("[index.importance_floors]\ndocs = 0.8\n", encoding="utf-8")
    assert load_config(paths).index.importance_floors["DOCS"] == 0.8


def test_sources_round_trip_through_torsor_toml(tmp_path):
    paths = TorsorPaths(tmp_path)
    config = TorsorConfig()
    config.memory.sources = ["README.md", "website/docs/**/*.md"]
    save_config(paths, config)
    assert load_config(paths).memory.sources == ["README.md", "website/docs/**/*.md"]


# ---- adapters ----

def test_stats_counts_project_docs(tmp_path):
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    _store(tmp_path)
    save_config(TorsorPaths(tmp_path), TorsorConfig())
    _write(tmp_path, "docs/a.md", "# A\n")
    _write(tmp_path, "README.md", "# R\n")
    CliRunner().invoke(app, ["index", "--root", str(tmp_path)])
    out = CliRunner().invoke(app, ["stats", "--root", str(tmp_path)]).output
    assert "docs 2" in out


def test_the_cli_indexes_docs_from_torsor_toml(tmp_path):
    """The setting has to reach the Store the adapter builds, or it does nothing."""
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    _store(tmp_path)
    save_config(TorsorPaths(tmp_path), TorsorConfig())
    _write(tmp_path, "docs/gateway.md", "# Message routing\n\nThe gateway routes messages.\n")
    out = CliRunner().invoke(app, ["recall", "gateway", "routes", "--root", str(tmp_path)]).output
    assert "Message routing (DOCS)" in out


def test_the_mcp_server_indexes_docs_from_torsor_toml(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _store(tmp_path)
    save_config(TorsorPaths(tmp_path), TorsorConfig())
    _write(tmp_path, "docs/gateway.md", "# Message routing\n\nThe gateway routes messages.\n")
    server = build_server(tmp_path)
    text = anyio.run(lambda: server.call_tool("recall", {"query": "gateway routes"}))[0][0].text
    assert "Message routing (DOCS)" in text


def test_db_rows_record_the_docs_tier(tmp_path):
    store = _store(tmp_path)
    _write(tmp_path, "docs/a.md", "# A\n\ncontent\n")
    ops.recall(store, TorsorConfig(), "content")
    conn = db.connect(store.paths.index_db)
    try:
        tiers = {r["tier"] for r in conn.execute("SELECT tier FROM notes WHERE path LIKE '%docs/a.md'")}
    finally:
        conn.close()
    assert tiers == {int(Tier.DOCS)}


# ---- unfilled seed templates carry no information ----
#
# Found by the same run: on a freshly initialized project the SessionStart hook
# injected ~283 tokens of placeholder text into every session and again after
# every compaction — "_Describe the product in 2-3 sentences._" — and recall
# ranked the unfilled System Patterns template first or second for unrelated
# questions, because the architecture tier carries a 1.4 weight.

def _fresh(tmp_path):
    from torsor_helper.paths import TorsorPaths as _P

    store = Store(_P(tmp_path), doc_sources=list(DEFAULT))
    store.scaffold()
    return store


def test_bootstrap_never_injects_placeholder_text(tmp_path):
    text = ops.bootstrap_session(_fresh(tmp_path), TorsorConfig())
    assert "_Describe the product" not in text
    assert "Layers, modules, how they communicate" not in text


def test_bootstrap_includes_a_section_once_it_is_filled_in(tmp_path):
    store = _fresh(tmp_path)
    store.paths.charter.write_text("# Charter\n\nWe build a routing gateway for chat platforms.\n",
                                   encoding="utf-8")
    text = ops.bootstrap_session(store, TorsorConfig())
    assert "routing gateway for chat platforms" in text


def test_the_session_start_digest_on_a_fresh_project_is_short_and_says_why(tmp_path):
    from torsor_helper.budget import estimate_tokens

    text = ops.session_start_context(_fresh(tmp_path), TorsorConfig())
    assert text is not None
    assert estimate_tokens(text) < 150, estimate_tokens(text)
    assert "seed template" in text


def test_the_session_start_digest_says_project_docs_are_searchable(tmp_path):
    store = _fresh(tmp_path)
    _write(tmp_path, "docs/a.md", "# A\n")
    _write(tmp_path, "README.md", "# R\n")
    assert "2 project doc" in ops.session_start_context(store, TorsorConfig())


def test_recall_never_returns_an_unfilled_template(tmp_path):
    store = _fresh(tmp_path)
    hits = ops.recall(store, TorsorConfig(), "architecture layers modules conventions").hits
    assert not [h for h in hits if h.title in ("System Patterns", "Charter", "Tech Context")]


def test_a_filled_template_is_recalled(tmp_path):
    store = _fresh(tmp_path)
    store.paths.system_patterns.write_text(
        "# System Patterns\n\nEvery adapter talks to the gateway through a queue.\n", encoding="utf-8")
    hits = ops.recall(store, TorsorConfig(), "adapter gateway queue").hits
    assert hits and hits[0].title == "System Patterns"


def test_get_intent_skips_unfilled_templates(tmp_path):
    text = ops.get_intent(_fresh(tmp_path), TorsorConfig())
    assert "Layers, modules, how they communicate" not in text


def test_the_coach_and_everything_else_agree_on_what_unfilled_means(tmp_path):
    """One definition. The Coach compared stripped text with the seed on its own."""
    from torsor_helper import templates

    store = _fresh(tmp_path)
    assert templates.is_unfilled(store.paths, store.paths.charter)
    store.paths.charter.write_text(store.paths.charter.read_text() + "\nWe route messages.\n")
    assert not templates.is_unfilled(store.paths, store.paths.charter)
    assert not templates.is_unfilled(store.paths, tmp_path / "docs" / "whatever.md")


def test_a_template_indexed_by_an_older_version_is_swept(tmp_path):
    """The check has to run before the stat pre-screen, or an unchanged seed that
    is already in the index is skipped as unchanged and stays there forever —
    which is every existing project."""
    store = _fresh(tmp_path)
    conn = db.connect(store.paths.index_db)
    try:
        from torsor_helper.embeddings import HashingEmbedder
        from torsor_helper.indexer import reindex

        # Simulate the old behaviour: index the seed as an ordinary note.
        note = store.read_note(store.paths.system_patterns)
        st = store.paths.system_patterns.stat()
        db.upsert_note(conn, store.paths.system_patterns.as_posix(), note.content_hash, int(note.tier),
                       note.frontmatter.type, None, note.title, "", "active",
                       mtime_ns=st.st_mtime_ns, size=st.st_size)
        db.replace_fts(conn, store.paths.system_patterns.as_posix(), note.title, note.body)
        conn.commit()
        reindex(store, conn, HashingEmbedder(384))
        rows = conn.execute("SELECT path FROM notes WHERE path LIKE '%system-patterns.md'").fetchall()
    finally:
        conn.close()
    assert rows == []


def test_rules_never_write_a_placeholder_principle_into_agent_instructions(tmp_path):
    """`torsor rules --write` put "_e.g. local-first; Markdown is the source of
    truth._" into the user's AGENTS.md as a non-negotiable principle."""
    store = _fresh(tmp_path)
    assert "e.g. local-first" not in ops.agent_rules(store, TorsorConfig())


def test_the_primer_never_carries_placeholder_text(tmp_path):
    """`primer --write` lands in AGENTS.md / CLAUDE.md, loaded into every session:
    the whole seed charter and "_Placeholder for now._" were paid for each time."""
    text = ops.project_primer(_fresh(tmp_path), TorsorConfig())
    assert "_Describe the product" not in text
    assert "Placeholder for now" not in text
    assert "e.g. local-first" not in text


def test_the_primer_includes_a_filled_charter(tmp_path):
    store = _fresh(tmp_path)
    store.paths.charter.write_text("# Charter\n\nA message gateway for chat platforms.\n", encoding="utf-8")
    assert "A message gateway for chat platforms" in ops.project_primer(store, TorsorConfig())


def test_an_auto_handoff_does_not_copy_placeholders_into_the_journal(tmp_path):
    store = _fresh(tmp_path)
    ops.auto_handoff(store, TorsorConfig())
    journal = "".join(p.read_text() for p in store.paths.journal_dir.glob("*.md"))
    assert "_Unresolved decisions._" not in journal
    assert "Describe" not in journal


def test_llms_txt_does_not_summarise_the_project_with_a_placeholder(tmp_path):
    store = _fresh(tmp_path)
    ops.export_project(store, TorsorConfig())
    text = store.paths.llms_txt.read_text()
    assert "Describe the product" not in text


def test_mcp_resources_say_a_note_is_unfilled_instead_of_serving_the_seed(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _fresh(tmp_path)
    server = build_server(tmp_path)
    contents = anyio.run(lambda: server.read_resource("torsor://charter"))
    text = "".join(getattr(c, "content", "") or getattr(c, "text", "") for c in contents)
    assert "Describe the product" not in text
    assert "seed template" in text


# ---- test code is systematically over-ranked ----
#
# Test names are written as prose about behaviour — test_webhook_routes_message —
# so a map note listing them matches a natural-language question better than
# the implementation it tests. On the real project, test-file map notes took 2
# to 4 of the top 5 recall slots for 7 of 7 questions; weighted down, they were
# replaced by the implementation files or by relevant docs in every one.

@pytest.mark.parametrize("path, expected", [
    ("tests/gateway/test_x.py", True), ("test/unit.py", True), ("pkg/test_x.py", True),
    ("pkg/x_test.py", True), ("svc/handler_test.go", True), ("src/a.test.ts", True),
    ("src/a.spec.tsx", True), ("src/__tests__/a.js", True), ("conftest.py", True),
    ("gateway/router.py", False), ("src/testing_utils.py", False), ("contest/a.py", False),
    ("src/latest.ts", False),
])
def test_is_test_path(path, expected):
    from torsor_helper.paths import is_test_path

    assert is_test_path(path) is expected


def _mapped_with_a_test(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "router.py").write_text(
        "def route_message(msg):\n    return msg\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_router.py").write_text(
        "def test_route_message_routes_a_message():\n    pass\n"
        "def test_route_message_routes_every_message():\n    pass\n", encoding="utf-8")
    ops.map_repo(store, TorsorConfig())
    return store


def test_the_implementation_outranks_the_tests_that_describe_it(tmp_path):
    store = _mapped_with_a_test(tmp_path)
    hits = [h for h in ops.recall(store, TorsorConfig(), "route message").hits if h.tier is Tier.MAP]
    titles = [h.title for h in hits]
    assert titles.index("gateway/router.py") < titles.index("tests/test_router.py")


def test_asking_about_a_test_still_finds_it(tmp_path):
    """Weighted down, not removed."""
    store = _mapped_with_a_test(tmp_path)
    titles = [h.title for h in ops.recall(store, TorsorConfig(), "test_route_message_routes_every_message").hits]
    assert "tests/test_router.py" in titles


def test_the_fresh_project_digest_is_not_cut_mid_word(tmp_path):
    """The Coach's share of the session digest was a fixed 8% even when every
    section above it was empty, so on a fresh project its most useful line
    ended in "System patterns is st…"."""
    text = ops.session_start_context(_fresh(tmp_path), TorsorConfig())
    assert "[truncated]" not in text and "…" not in text
