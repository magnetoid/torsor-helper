import json
from pathlib import Path

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


@needs_ts
def test_js_subpath_import_not_flagged(tmp_path):
    # '#internal/x' is a Node subpath import (package.json "imports" field),
    # not a bare package specifier — must not be flagged as phantom (ADR 0006).
    (tmp_path / "a.ts").write_text("import x from '#internal/x';\n")
    assert deps.unknown_imports(tmp_path, ["a.ts"]) == []


@needs_ts
def test_js_known_survives_node_modules_permission_error(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4"}}))
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "a.ts").write_text("import _ from 'lodash/fp';\nimport ghost from 'left-padd';\n")

    real_iterdir = Path.iterdir

    def raising_iterdir(self):
        if self.name == "node_modules":
            raise PermissionError("denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", raising_iterdir)

    result = deps.unknown_imports(tmp_path, ["a.ts"])
    assert [(u["name"], u["line"]) for u in result] == [("left-padd", 2)]


@needs_ts
def test_js_known_computed_once_per_call(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4"}}))
    (tmp_path / "a.ts").write_text("import _ from 'lodash';\n")
    (tmp_path / "b.ts").write_text("import _ from 'lodash';\n")

    calls = []
    original = deps._js_known

    def counting(root):
        calls.append(root)
        return original(root)

    monkeypatch.setattr(deps, "_js_known", counting)

    deps.unknown_imports(tmp_path, ["a.ts", "b.ts"])
    assert len(calls) == 1


needs_go = pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")


@needs_go
def test_go_phantom_import_path(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.22\n\nrequire (\n\tgithub.com/real/lib v1.0.0\n)\n")
    (tmp_path / "a.go").write_text(
        'package a\nimport (\n\t"fmt"\n\t"example.com/app/util"\n\t"github.com/real/lib/sub"\n\t"github.com/ghost/pkg"\n)\n')
    unknown = deps.unknown_imports(tmp_path, ["a.go"])
    assert [(u["name"], u["line"]) for u in unknown] == [("github.com/ghost/pkg", 6)]


@needs_go
def test_go_single_line_require_recognised(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module example.com/app\n\ngo 1.22\n\nrequire github.com/x/y v1.0.0\n"
    )
    (tmp_path / "a.go").write_text('package a\nimport (\n\t"fmt"\n\t"github.com/x/y/sub"\n)\n')
    assert deps.unknown_imports(tmp_path, ["a.go"]) == []


@needs_go
def test_go_replace_directive_left_side_known(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module example.com/app\n\ngo 1.22\n\nreplace github.com/old/pkg => github.com/new/pkg v1.2.3\n"
    )
    (tmp_path / "a.go").write_text('package a\nimport "github.com/old/pkg"\n')
    assert deps.unknown_imports(tmp_path, ["a.go"]) == []


@needs_go
def test_go_no_gomod_reports_only_non_stdlib(tmp_path):
    (tmp_path / "a.go").write_text(
        'package a\nimport (\n\t"fmt"\n\t"os"\n\t"github.com/ghost/pkg"\n)\n'
    )
    unknown = deps.unknown_imports(tmp_path, ["a.go"])
    assert [(u["name"], u["line"]) for u in unknown] == [("github.com/ghost/pkg", 5)]


def test_go_path_yields_nothing_without_languages_extra(tmp_path, monkeypatch):
    # Without the [languages] extra, import_specifiers() returns [] for Go,
    # so the Go phantom-import path must yield nothing rather than erroring.
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    (tmp_path / "a.go").write_text('package a\nimport "github.com/ghost/pkg"\n')
    assert deps.unknown_imports(tmp_path, ["a.go"]) == []


def test_unknown_imports_mixed_python_and_go_reports_python_phantom(tmp_path):
    # The dispatch added for Go must not disturb the existing Python path.
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
    (tmp_path / "a.go").write_text('package a\nimport "github.com/ghost/pkg"\n')

    found = deps.unknown_imports(tmp_path, ["a.py", "a.go"])
    assert {f["name"] for f in found if f["file"] == "a.py"} == {"totallyfakepkg"}


@needs_go
def test_go_known_prefixes_computed_once_per_call(tmp_path, monkeypatch):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
    (tmp_path / "a.go").write_text('package a\nimport "github.com/ghost/pkg"\n')
    (tmp_path / "b.go").write_text('package a\nimport "github.com/ghost/pkg"\n')

    calls = []
    original = deps._go_known_prefixes

    def counting(root):
        calls.append(root)
        return original(root)

    monkeypatch.setattr(deps, "_go_known_prefixes", counting)

    deps.unknown_imports(tmp_path, ["a.go", "b.go"])
    assert len(calls) == 1


@needs_ts
def test_translation_helper_call_is_not_a_phantom_import(tmp_path):
    # `t('nav.home')` is a plain function call, not a require() — it used to be
    # reported as the phantom dependency "nav.home".
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {}}))
    (tmp_path / "a.ts").write_text("const label = t('nav.home');\nexport const x = label;\n")
    assert deps.unknown_imports(tmp_path, ["a.ts"]) == []
