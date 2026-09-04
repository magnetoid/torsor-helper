import json

import pytest

from torsor_helper import deps, languages

needs_ts = pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")


@needs_ts
def test_js_phantom_bare_specifier(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"lodash": "^4"}, "devDependencies": {"@types/node": "*"}})
    )
    (tmp_path / "node_modules" / "@scope" / "pkg").mkdir(parents=True)
    (tmp_path / "a.ts").write_text(
        "import _ from 'lodash/fp';\nimport fs from 'node:fs';\nimport path from 'path';\n"
        "import x from '@scope/pkg/sub';\nimport { y } from './local';\nimport ghost from 'left-padd';\n"
    )
    unknown = deps.unknown_imports(tmp_path, ["a.ts"])
    assert [(u["name"], u["line"]) for u in unknown] == [("left-padd", 6)]


def test_js_path_yields_nothing_without_languages_extra(tmp_path, monkeypatch):
    # Without the [languages] extra, import_specifiers() returns [] for JS/TS,
    # so the JS phantom-import path must yield nothing rather than erroring.
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    (tmp_path / "a.ts").write_text("import ghost from 'left-padd';\n")
    assert deps.unknown_imports(tmp_path, ["a.ts"]) == []


def test_unknown_imports_mixed_python_and_ts_reports_python_phantom(tmp_path):
    # The dispatch added for JS/TS must not disturb the existing Python path.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    sp = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages"
    info = sp / "requests-1.0.0.dist-info"
    info.mkdir(parents=True)
    (info / "top_level.txt").write_text("requests\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["pyyaml>=6", "rich"]\n'
    )
    (tmp_path / "a.py").write_text(
        "import os\nimport requests\nimport pkg\nimport yaml\nimport rich\nimport totallyfakepkg\n"
    )
    (tmp_path / "a.ts").write_text("import ghost from 'left-padd';\n")

    found = deps.unknown_imports(tmp_path, ["a.py", "a.ts"])
    assert {f["name"] for f in found if f["file"] == "a.py"} == {"totallyfakepkg"}
