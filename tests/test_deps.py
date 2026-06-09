from torsor_helper import deps


def _venv_with(tmp_path, *top_levels):
    sp = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages"
    for tl in top_levels:
        info = sp / f"{tl}-1.0.0.dist-info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "top_level.txt").write_text(tl + "\n")


def test_stdlib_names_present():
    names = deps.stdlib_names()
    assert "os" in names and "sys" in names and "json" in names


def test_installed_import_names_from_venv(tmp_path):
    _venv_with(tmp_path, "requests")
    assert "requests" in deps.installed_import_names(tmp_path)


def test_first_party_names(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "solo.py").write_text("x = 1\n")
    names = deps.first_party_names(tmp_path)
    assert "pkg" in names and "solo" in names


def test_declared_import_names_with_alias(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["pyyaml>=6", "rich"]\n'
    )
    names = deps.declared_import_names(tmp_path)
    assert "yaml" in names  # pyyaml -> yaml alias
    assert "rich" in names


def test_unknown_imports_flags_only_hallucinated(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    _venv_with(tmp_path, "requests")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["pyyaml>=6", "rich"]\n'
    )
    (tmp_path / "app.py").write_text(
        "import os\n"            # stdlib
        "import requests\n"      # installed in .venv
        "import pkg\n"           # first-party
        "import yaml\n"          # declared (pyyaml alias)
        "import rich\n"          # declared
        "import totallyfakepkg\n"  # hallucinated -> flag
        "from . import sibling\n"  # relative -> skip
    )
    found = deps.unknown_imports(tmp_path, ["app.py"])
    assert {f["name"] for f in found} == {"totallyfakepkg"}
    assert found[0]["file"] == "app.py" and found[0]["line"] == 6


def test_unknown_imports_skips_syntax_errors(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:\n")
    assert deps.unknown_imports(tmp_path, ["bad.py"]) == []
