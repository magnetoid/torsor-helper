from pathlib import Path

from torsor_helper.paths import TorsorPaths
from torsor_helper.templates import seed_files


def test_seed_files_cover_every_tier(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    files = seed_files(paths)
    assert paths.charter in files
    assert paths.system_patterns in files
    assert paths.tech_context in files
    assert paths.active_context in files
    assert paths.progress in files
    assert paths.map_overview in files
    first_adr = paths.decisions_dir / "0001-adopt-torsor-helper.md"
    assert first_adr in files
    for path, content in files.items():
        assert content.startswith("---\n"), f"{path} missing frontmatter"
        assert "# " in content, f"{path} missing H1 title"
