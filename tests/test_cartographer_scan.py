from torsor_helper.cartographer import iter_source_files, scan_repo


def _make_repo(root):
    (root / "pkg").mkdir()
    (root / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (root / "app.py").write_text("from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n")
    (root / ".venv").mkdir()
    (root / ".venv" / "junk.py").write_text("def should_not_appear():\n    pass\n")
    (root / ".torsor").mkdir()
    (root / ".torsor" / "x.py").write_text("def nope():\n    pass\n")


def test_iter_source_files_skips_ignored(tmp_path):
    _make_repo(tmp_path)
    files = [p.relative_to(tmp_path).as_posix() for p in iter_source_files(tmp_path)]
    assert "app.py" in files
    assert "pkg/dates.py" in files
    assert not any(".venv" in f or ".torsor" in f for f in files)


def test_scan_repo_collects_symbols_and_refs(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path)
    names = {s.name for s in syms}
    assert {"format_date", "run"} <= names
    assert "should_not_appear" not in names
    fmt = next(s for s in syms if s.name == "format_date")
    assert fmt.refs >= 1
    assert fmt.module == "pkg/dates.py"


def test_scan_repo_explicit_paths(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path, paths=["app.py"])
    assert {s.module for s in syms} == {"app.py"}


def test_scan_handles_utf8_bom(tmp_path):
    (tmp_path / "bom.py").write_text("\ufeffdef f():\n    pass\n", encoding="utf-8")
    syms = scan_repo(tmp_path)
    assert any(s.name == "f" for s in syms)
