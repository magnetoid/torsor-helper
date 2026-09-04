import pytest

from torsor_helper import languages
from torsor_helper.guard import violations_for_file
from torsor_helper.models import Rule


def _rule(target, scope):
    return Rule(kind="forbid_import", target=target, scope=scope, source="ADR 9", message="no")


@pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
def test_typescript_forbid_import_matches_specifier_prefix():
    text = "import x from 'lodash/fp';\nimport { db } from '../internal/db';\n"
    assert [v.line for v in violations_for_file("src/a.ts", text, _rule("lodash", "**/*.ts"))] == [1]
    assert [v.line for v in violations_for_file("src/a.ts", text, _rule("../internal", "**/*.ts"))] == [2]
    assert violations_for_file("src/a.ts", text, _rule("react", "**/*.ts")) == []


@pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")
def test_go_forbid_import_matches_path_prefix():
    text = 'package a\nimport (\n\t"fmt"\n\t"example.com/app/internal/db"\n)\n'
    assert [v.line for v in violations_for_file("a.go", text, _rule("example.com/app/internal", "**/*.go"))] == [4]


def test_non_python_without_extra_is_silent(monkeypatch):
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert violations_for_file("a.ts", "import x from 'lodash';\n", _rule("lodash", "**/*.ts")) == []


@pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
def test_typescript_annotated_line_still_yields_specifier():
    # A type annotation on the following line must not stop the typescript
    # grammar (vs. the plain javascript one) from parsing the import correctly.
    text = "import x from 'lodash/fp';\nconst n: number = 1;\n"
    assert [v.line for v in violations_for_file("src/a.ts", text, _rule("lodash", "**/*.ts"))] == [1]
