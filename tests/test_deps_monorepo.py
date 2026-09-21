"""Dependency resolution in a monorepo.

Found by running torsor on a real project rather than on itself. The Coach's
phantom-dependency check reported 1 966 "possible hallucinated dependencies" on
a working JS/TS + Python monorepo, 1 764 of them in JS/TS — `react`, `vitest`,
`@/lib`, `@janus/ink` — every one a false alarm. ADR 0006 promises the opposite
trade: a missed phantom over a false alarm.

The cause was structural. Only the ROOT package.json and the ROOT node_modules
were read, so every dependency declared by a nested app was unknown, and so was
every tsconfig path alias and every sibling workspace package. The model here is
Node's own: a file sees the manifests of every directory between it and the
root.

Each test keeps one genuine phantom (`left-padd`) as a control, so a resolver
that simply stopped flagging anything would fail here too.
"""
from __future__ import annotations

import json

import pytest

from torsor_helper import deps, languages

needs_ts = pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
needs_go = pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


def _names(root, files):
    return sorted({u["name"] for u in deps.unknown_imports(root, files)})


def _monorepo(root):
    _write(root, "package.json", json.dumps({
        "name": "acme", "workspaces": ["apps/*", "packages/*"],
        "devDependencies": {"typescript": "*"},
    }))
    _write(root, "apps/desktop/package.json", json.dumps({
        "name": "desktop", "dependencies": {"react": "*"}, "devDependencies": {"vitest": "*"},
    }))
    _write(root, "packages/ink/package.json", json.dumps({"name": "@acme/ink"}))


@needs_ts
def test_a_nested_app_sees_its_own_manifest(tmp_path):
    _monorepo(tmp_path)
    f = _write(tmp_path, "apps/desktop/src/app.tsx",
               "import React from 'react';\nimport { it } from 'vitest';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_a_nested_app_also_sees_the_root_manifest(tmp_path):
    """Node walks up through every node_modules; hoisted root deps are visible."""
    _monorepo(tmp_path)
    f = _write(tmp_path, "apps/desktop/src/a.ts", "import ts from 'typescript';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_a_sibling_apps_dependency_is_not_visible(tmp_path):
    """The precision half: resolution is by ancestry, not a repo-wide union of
    every manifest — `react` declared by desktop is not declared for a tool that
    lives beside it. That is a real phantom in the tool, and must stay flagged."""
    _monorepo(tmp_path)
    _write(tmp_path, "tools/cli/package.json", json.dumps({"name": "cli", "dependencies": {}}))
    f = _write(tmp_path, "tools/cli/index.ts", "import React from 'react';\n")
    assert _names(tmp_path, [f]) == ["react"]


@needs_ts
def test_a_workspace_package_is_first_party_everywhere(tmp_path):
    _monorepo(tmp_path)
    f = _write(tmp_path, "apps/desktop/src/b.ts",
               "import { Box } from '@acme/ink';\nimport sub from '@acme/ink/jsx';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_an_empty_scope_is_an_alias_not_a_package(tmp_path):
    """npm scopes cannot be empty, so `@/x` is a path alias by definition — no
    config needed. 234 of the false alarms were `@/lib` alone."""
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    f = _write(tmp_path, "src/a.ts",
               "import { cn } from '@/lib/utils';\nimport c from '@/components';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_tsconfig_paths_are_aliases(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "tsconfig.json", json.dumps({"compilerOptions": {"paths": {
        "~app/*": ["src/*"], "@shared": ["../shared/src/index.ts"],
    }}}))
    f = _write(tmp_path, "src/a.ts",
               "import a from '~app/thing';\nimport s from '@shared';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_a_tsconfig_with_comments_and_trailing_commas_still_parses(tmp_path):
    """tsconfig is JSONC. json.loads raises on it, and the real project's
    web/tsconfig.app.json has /* comments */ right beside its paths block."""
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "web/tsconfig.app.json", """{
      // the app
      "compilerOptions": {
        /* Aliases */
        "paths": { "ui/*": ["./src/ui/*"], },
      },
    }""")
    f = _write(tmp_path, "web/src/a.ts", "import b from 'ui/button';\nimport x from 'ui-kit';\n")
    assert _names(tmp_path, [f]) == ["ui-kit"]


@pytest.mark.parametrize("text, expected", [
    ('{"a": [1, 2,], // last\n}', {"a": [1, 2]}),
    ('{"a": 1, /* last */ }', {"a": 1}),
    ('{"a": "x,}y", }', {"a": "x,}y"}),
    ('{"a": "q\\"uote // not a comment"}', {"a": 'q"uote // not a comment'}),
    ('{"s": "https://json.schemastore.org/tsconfig"}', {"s": "https://json.schemastore.org/tsconfig"}),
])
def test_jsonc(text, expected):
    """The first version kept a trailing comma whenever a comment sat between it
    and the closing brace — found by feeding it edge cases after the suite was
    already green, which is the order to do it in."""
    assert deps._loads_jsonc(text) == expected


@needs_ts
def test_a_url_inside_a_string_is_not_mistaken_for_a_comment(tmp_path):
    """Stripping `//` naively would cut "https://..." in half and break the file."""
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "tsconfig.json",
           '{"$schema": "https://json.schemastore.org/tsconfig", '
           '"compilerOptions": {"paths": {"$lib/*": ["src/lib/*"]}}}')
    f = _write(tmp_path, "src/a.ts", "import u from '$lib/u';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_a_catch_all_alias_resolves_against_the_filesystem(tmp_path):
    """`"*": ["src/*"]` (or a bare `baseUrl`) makes any bare specifier possibly
    local. Treating it as a wildcard would switch the check off for the whole
    project; ignoring it would flag every local import. So resolve it: local only
    if the target actually exists."""
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"*": ["src/*"]}}}))
    _write(tmp_path, "src/components/Button.tsx", "export const B = 1;\n")
    f = _write(tmp_path, "src/a.ts", "import B from 'components/Button';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_a_bare_base_url_resolves_like_a_catch_all(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": "src"}}))
    _write(tmp_path, "src/utils/index.ts", "export const u = 1;\n")
    f = _write(tmp_path, "src/a.ts", "import u from 'utils';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_an_unparseable_tsconfig_does_not_raise(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"name": "x", "dependencies": {"react": "*"}}))
    _write(tmp_path, "tsconfig.json", "{ this is not json at all")
    f = _write(tmp_path, "a.ts", "import R from 'react';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_nested_node_modules_count(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    (tmp_path / "apps/web/node_modules/@scope/pkg").mkdir(parents=True)
    (tmp_path / "apps/web/node_modules/plain").mkdir(parents=True)
    f = _write(tmp_path, "apps/web/a.ts",
               "import a from '@scope/pkg';\nimport b from 'plain';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@needs_ts
def test_manifests_under_node_modules_are_never_read(tmp_path, monkeypatch):
    """A real node_modules holds thousands of package.json files; walking into
    it would make this check slower than the map."""
    _write(tmp_path, "package.json", json.dumps({"name": "x"}))
    _write(tmp_path, "node_modules/huge/package.json", json.dumps({"name": "huge"}))
    read = []
    real = deps._read_manifest

    def spy(path):
        read.append(path.as_posix())
        return real(path)

    monkeypatch.setattr(deps, "_read_manifest", spy)
    f = _write(tmp_path, "a.ts", "import g from 'left-padd';\n")
    deps.unknown_imports(tmp_path, [f])
    assert not any("node_modules" in p for p in read)


@needs_go
def test_a_nested_go_module_sees_its_own_requires(tmp_path):
    _write(tmp_path, "go.mod", "module example.com/root\n\ngo 1.22\n")
    _write(tmp_path, "svc/go.mod",
           "module example.com/svc\n\ngo 1.22\n\nrequire github.com/lib/pq v1.10.0\n")
    f = _write(tmp_path, "svc/main.go",
               'package main\nimport (\n  "github.com/lib/pq"\n  "github.com/ghost/pkg"\n)\n')
    assert _names(tmp_path, [f]) == ["github.com/ghost/pkg"]


@needs_go
def test_a_go_module_can_import_a_sibling_local_module(tmp_path):
    _write(tmp_path, "shared/go.mod", "module example.com/shared\n\ngo 1.22\n")
    _write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
    f = _write(tmp_path, "svc/main.go",
               'package main\nimport (\n  "example.com/shared/util"\n  "github.com/ghost/pkg"\n)\n')
    assert _names(tmp_path, [f]) == ["github.com/ghost/pkg"]


def test_resolution_is_built_once_per_call(tmp_path, monkeypatch):
    """Per-file manifest discovery must not become a per-file repo walk."""
    _monorepo(tmp_path)
    files = [_write(tmp_path, f"apps/desktop/src/f{i}.ts", "import React from 'react';\n") for i in range(20)]
    walks = []
    real = deps._manifest_index

    def counting(root):
        walks.append(root)
        return real(root)

    monkeypatch.setattr(deps, "_manifest_index", counting)
    deps.unknown_imports(tmp_path, files)
    assert len(walks) == 1


# ---- Python: the same ancestry model ----
#
# 202 Python findings on the same project, in three kinds. Scripts importing the
# helper module beside them (`from _common import x`, with scripts/_common.py
# right there): Python puts a script's own directory on sys.path, so that is
# first-party by the language's definition. Packages declared under a different
# distribution name (`discord.py` -> discord, `firecrawl-py` -> firecrawl). And
# genuinely undeclared direct imports, which are real findings and stay.


def test_a_script_can_import_the_module_beside_it(tmp_path):
    f = _write(tmp_path, "skills/comfy/scripts/run.py", "from _common import x\nimport left_padd\n")
    _write(tmp_path, "skills/comfy/scripts/_common.py", "x = 1\n")
    assert _names(tmp_path, [f]) == ["left_padd"]


def test_a_module_in_an_ancestor_directory_is_first_party(tmp_path):
    """Plugin loaders and test runners put an ancestor on sys.path."""
    f = _write(tmp_path, "plugins/memory/holo/retrieval.py", "import holo\nimport left_padd\n")
    _write(tmp_path, "plugins/memory/holo/__init__.py", "")
    _write(tmp_path, "plugins/memory/holo.py", "")
    assert _names(tmp_path, [f]) == ["left_padd"]


def test_a_module_in_a_sibling_subtree_is_not_first_party(tmp_path):
    """The precision half: ancestry, not "exists anywhere in the repo"."""
    f = _write(tmp_path, "a/x.py", "import helper\n")
    _write(tmp_path, "b/helper.py", "")
    assert _names(tmp_path, [f]) == ["helper"]


@pytest.mark.parametrize("dist, module", [
    ("discord.py", "discord"),
    ("firecrawl-py", "firecrawl"),
    ("honcho-ai", "honcho"),
    ("parallel-web", "parallel"),
    ("ruamel.yaml", "ruamel"),
    ("python-telegram-bot", "telegram"),
    ("PyNaCl", "nacl"),
])
def test_a_distribution_declared_under_another_name_is_known(tmp_path, dist, module):
    _write(tmp_path, "pyproject.toml", f'[project]\nname = "x"\ndependencies = ["{dist}>=1"]\n')
    f = _write(tmp_path, "app.py", f"import {module}\nimport left_padd\n")
    assert _names(tmp_path, [f]) == ["left_padd"]


def test_a_nested_requirements_file_governs_its_own_subtree(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\ndependencies = []\n')
    _write(tmp_path, "skills/dcf/requirements.txt", "openpyxl>=3\n")
    inside = _write(tmp_path, "skills/dcf/model.py", "import openpyxl\nimport left_padd\n")
    outside = _write(tmp_path, "other/model.py", "import openpyxl\n")
    assert _names(tmp_path, [inside]) == ["left_padd"]
    assert _names(tmp_path, [outside]) == ["openpyxl"]


@needs_ts
def test_a_types_package_makes_its_module_importable(tmp_path):
    """`import type { Element } from 'hast'` resolves through @types/hast."""
    _write(tmp_path, "package.json", json.dumps({"name": "x", "devDependencies": {
        "@types/hast": "*", "@types/babel__core": "*",
    }}))
    f = _write(tmp_path, "a.ts",
               "import type { E } from 'hast';\nimport type { B } from '@babel/core';\nimport g from 'left-padd';\n")
    assert _names(tmp_path, [f]) == ["left-padd"]


@pytest.mark.parametrize("guard", [
    "except ImportError:", "except ModuleNotFoundError:", "except (ImportError, OSError):",
    "except Exception:", "except:",
])
def test_an_import_guarded_against_absence_is_optional_by_design(tmp_path, guard):
    """57 of the 119 Python findings on the real project were inside a
    try/except ImportError — the code itself saying the package may not be
    there. An agent hallucinating a package does not wrap it in that guard;
    it is the canonical optional-dependency idiom, and torsor uses it too."""
    f = _write(tmp_path, "a.py", f"try:\n    import fastembed\n{guard}\n    fastembed = None\nimport left_padd\n")
    assert _names(tmp_path, [f]) == ["left_padd"]


def test_a_guard_that_catches_something_else_does_not_count(tmp_path):
    f = _write(tmp_path, "a.py", "try:\n    import left_padd\nexcept KeyError:\n    pass\n")
    assert _names(tmp_path, [f]) == ["left_padd"]


def test_an_import_in_the_handler_is_not_guarded(tmp_path):
    """Only the try body is protected; the fallback in the except clause runs
    exactly when the first import failed, so it had better exist."""
    f = _write(tmp_path, "a.py", "try:\n    import ujson as json\nexcept ImportError:\n    import left_padd as json\n")
    assert _names(tmp_path, [f]) == ["left_padd"]


# ---- the other bug the same run found: a check of nothing that reads as a pass ----

def _clean_repo(tmp_path):
    import subprocess

    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    Store(TorsorPaths(tmp_path)).scaffold()
    _write(tmp_path, "app.py", "import left_padd\n")
    for args in (["init", "-q"], ["config", "user.email", "t@e.x"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)


def test_deps_on_a_clean_tree_says_it_checked_nothing(tmp_path):
    """The default is git-changed files, so on a clean checkout the list is
    empty — and "every import resolves to a known package" after checking zero
    files is exactly how the real project's 1 966 findings stayed hidden. The
    same bug `guard` had, fixed there in Phase 6 and never here."""
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    _clean_repo(tmp_path)
    result = CliRunner().invoke(app, ["deps", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "every import resolves" not in result.output
    assert "No files to check" in result.output


def test_deps_over_mcp_on_a_clean_tree_says_it_checked_nothing(tmp_path):
    import json

    import anyio

    from torsor_helper.server import build_server

    _clean_repo(tmp_path)
    server = build_server(tmp_path)

    async def call(**kw):
        return await server.call_tool("check_dependencies", kw)

    text = anyio.run(lambda: call())[0][0].text
    assert "every import resolves" not in text and "No files to check" in text
    payload = json.loads(anyio.run(lambda: call(as_json=True))[0][0].text)
    assert payload["checked"] == 0


def test_deps_with_explicit_files_still_finds_them(tmp_path):
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    _clean_repo(tmp_path)
    result = CliRunner().invoke(app, ["deps", "app.py", "--root", str(tmp_path)])
    assert "left_padd" in result.output


def test_the_statement_walk_reaches_every_place_an_import_can_live(tmp_path):
    """Walking statements instead of every node is what made this 15x faster;
    the risk is a construct it forgets to descend into, so name them all."""
    src = """
import p_top
def f():
    import p_func
    class C:
        def m(self):
            import p_method
if True:
    import p_if
else:
    import p_else
for _ in []:
    import p_for
while False:
    import p_while
with open(__file__):
    import p_with
try:
    pass
except KeyError:
    import p_handler
else:
    import p_try_else
finally:
    import p_finally
match 1:
    case 1:
        import p_match
async def g():
    async with x:
        import p_async_with
x = 1; import p_semicolon
if True: import p_inline_if
try: import p_inline_try
except KeyError: pass
import p_multi_a, p_multi_b as bb
from p_from.sub import (
    thing,
)
"""
    f = _write(tmp_path, "a.py", src)
    assert _names(tmp_path, [f]) == sorted([
        "p_top", "p_func", "p_method", "p_if", "p_else", "p_for", "p_while", "p_with",
        "p_handler", "p_try_else", "p_finally", "p_match", "p_async_with",
        "p_semicolon", "p_inline_if", "p_inline_try", "p_multi_a", "p_multi_b", "p_from",
    ])


def test_a_file_whose_imports_are_all_known_is_never_parsed(tmp_path, monkeypatch):
    """The parse is the floor — ~9 ms a file on a real project, 21 of its 28
    seconds. A file whose every import names something known cannot produce a
    finding, so it is not parsed at all."""
    import ast

    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\ndependencies = ["requests"]\n')
    clean = _write(tmp_path, "clean.py", "import os\nimport json, sys\nfrom requests import get\n")
    dirty = _write(tmp_path, "dirty.py", "import os\nimport left_padd\n")
    parsed = []
    real = ast.parse

    def spy(text, *a, **kw):
        parsed.append(text)
        return real(text, *a, **kw)

    monkeypatch.setattr(deps.ast, "parse", spy)
    assert _names(tmp_path, [clean, dirty]) == ["left_padd"]
    assert len(parsed) == 1, "only the file with an unknown candidate should be parsed"


def test_an_import_word_in_a_docstring_only_costs_a_parse(tmp_path):
    """The prefilter may over-approximate — the parse then decides."""
    f = _write(tmp_path, "a.py", '"""Usage:\n    import left_padd\n"""\nimport os\n')
    assert _names(tmp_path, [f]) == []


def test_a_projects_invalid_escapes_do_not_reach_the_users_stderr(tmp_path, recwarn):
    f = _write(tmp_path, "a.py", 'import re\nPATTERN = "\\d+"\nimport left_padd\n')
    assert _names(tmp_path, [f]) == ["left_padd"]
    assert not [w for w in recwarn if issubclass(w.category, SyntaxWarning)]
