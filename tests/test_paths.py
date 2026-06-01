from pathlib import Path

from torsor_helper.paths import TorsorPaths


def test_layout_under_dot_torsor(tmp_path: Path):
    p = TorsorPaths(tmp_path)
    assert p.base == tmp_path / ".torsor"
    assert p.charter == tmp_path / ".torsor" / "charter.md"
    assert p.system_patterns == tmp_path / ".torsor" / "architecture" / "system-patterns.md"
    assert p.decisions_dir == tmp_path / ".torsor" / "architecture" / "decisions"
    assert p.active_context == tmp_path / ".torsor" / "active" / "context.md"
    assert p.journal_dir == tmp_path / ".torsor" / "memory" / "journal"
    assert p.index_db == tmp_path / ".torsor" / ".index" / "torsor.db"


def test_journal_file_by_date(tmp_path: Path):
    p = TorsorPaths(tmp_path)
    assert p.journal_file("2026-06-01") == p.journal_dir / "2026-06-01.md"
