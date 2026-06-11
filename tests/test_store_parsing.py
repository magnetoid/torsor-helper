from torsor_helper.models import Frontmatter, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def test_parse_frontmatter_splits_meta_and_body():
    text = "---\ntype: charter\ntags: [a, b]\n---\n\n# Title\n\nBody line\n"
    fm, body = Store.parse_frontmatter(text)
    assert fm.type == "charter"
    assert fm.tags == ["a", "b"]
    assert body.strip().startswith("# Title")


def test_parse_frontmatter_without_meta_defaults_type_note():
    fm, body = Store.parse_frontmatter("# Just a title\n\ntext")
    assert fm.type == "note"
    assert body.strip().startswith("# Just a title")


def test_extract_wikilinks_dedupes_in_order():
    assert Store.extract_wikilinks("see [[alpha]] and [[beta]] and [[alpha]]") == ["alpha", "beta"]


def test_content_hash_is_stable_and_distinct():
    assert Store.content_hash("abc") == Store.content_hash("abc")
    assert Store.content_hash("abc") != Store.content_hash("abd")


def test_serialize_round_trips_through_parse():
    text = Store.serialize(Frontmatter(type="journal"), "Hello", "World body")
    fm, body = Store.parse_frontmatter(text)
    assert fm.type == "journal"
    assert "# Hello" in body and "World body" in body


def test_tier_for_path(tmp_path):
    paths = TorsorPaths(tmp_path)
    assert Store.tier_for_path(paths, paths.charter) is Tier.CHARTER
    assert Store.tier_for_path(paths, paths.system_patterns) is Tier.ARCHITECTURE
    assert Store.tier_for_path(paths, paths.map_overview) is Tier.MAP
    assert Store.tier_for_path(paths, paths.active_context) is Tier.ACTIVE
    assert Store.tier_for_path(paths, paths.journal_file("2026-06-01")) is Tier.EPISODIC


def test_parse_frontmatter_tolerates_unquoted_date():
    # A human editing Markdown writes `created: 2026-06-01`; YAML parses that as
    # a date object — it must coerce, never crash the indexing pipeline.
    text = "---\ntype: note\ncreated: 2026-06-01\n---\n\n# T\n\nbody\n"
    fm, body = Store.parse_frontmatter(text)
    assert fm.created == "2026-06-01"
    assert "body" in body


def test_parse_frontmatter_tolerates_invalid_yaml():
    fm, _ = Store.parse_frontmatter("---\nfoo: [unclosed\n---\n\n# T\n\nbody\n")
    assert fm.type == "note"


def test_parse_frontmatter_tolerates_scalar_frontmatter():
    fm, body = Store.parse_frontmatter("---\njust a string\n---\n\n# T\n\nbody\n")
    assert fm.type == "note"
    assert "# T" in body


def test_parse_frontmatter_tolerates_invalid_field_types():
    fm, _ = Store.parse_frontmatter("---\ntype: note\ntags: 7\n---\n\nbody\n")
    assert fm.type == "note"  # degrades, never raises


def test_parse_frontmatter_handles_empty_block():
    fm, body = Store.parse_frontmatter("---\n---\n\n# T\n\nbody\n")
    assert fm.type == "note"
    assert "---" not in body
