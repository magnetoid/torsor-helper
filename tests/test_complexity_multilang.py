import pytest

from torsor_helper import languages
from torsor_helper.coach.hotspots import _complexity


def test_python_complexity_is_unchanged(tmp_path):
    f = tmp_path / "a.py"
    text = "def f(x):\n    if x:\n        return 1\n    for i in x:\n        pass\n    return 0\n"
    f.write_text(text)
    assert _complexity(f) == text.count("\n") + 1 + 2  # if, for


def test_unknown_suffix_scores_zero(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("if if if\n")
    assert _complexity(f) == 0


@pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
def test_typescript_branches_count(tmp_path):
    f = tmp_path / "a.ts"
    text = "function f(x) {\n  if (x) { return 1 }\n  for (const i of x) {}\n  return x && y ? 1 : 0;\n}\n"
    f.write_text(text)
    assert _complexity(f) == text.count("\n") + 1 + 4  # if, for-of, &&, ternary


@pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")
def test_go_branches_count(tmp_path):
    f = tmp_path / "a.go"
    text = "package a\nfunc f(x int) int {\n\tif x > 0 { return 1 }\n\tfor i := 0; i < x; i++ {}\n\tswitch x { case 1: }\n\treturn 0\n}\n"
    f.write_text(text)
    assert _complexity(f) == text.count("\n") + 1 + 3  # if, for, case
