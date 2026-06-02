from torsor_helper.cartographer import extract_edges, scan_repo_with_edges

SRC = """
from m import c

def a():
    pass

def b():
    a()
    x = 1
    c()
    obj.foo()
"""


def test_extract_edges_resolves_same_module_and_import():
    edges = extract_edges(SRC, "mod.py")
    by = {(e.caller, e.referenced_name, e.role): e for e in edges}
    # same-module top-level def call resolves to this module
    assert ("b", "a", "call") in by
    assert by[("b", "a", "call")].resolved_module == "mod.py"
    # import-alias call resolves to the imported module
    assert ("b", "c", "call") in by
    assert by[("b", "c", "call")].resolved_module == "m"
    # attribute call on a non-alias receiver stays unresolved
    assert ("b", "foo", "call") in by
    assert by[("b", "foo", "call")].resolved_module is None
    # assignment target recorded as a write
    assert any(e.referenced_name == "x" and e.role == "write" for e in edges)


def test_syntax_error_yields_no_edges():
    assert extract_edges("def (:\n", "broken.py") == []


def test_refs_count_real_references_not_substrings(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (tmp_path / "app.py").write_text(
        "from pkg.dates import format_date\n\n"
        "def run():\n"
        "    # format_date mentioned in a comment must not inflate the count\n"
        "    return format_date(1)\n"
    )
    syms, edges = scan_repo_with_edges(tmp_path)
    fmt = next(s for s in syms if s.name == "format_date")
    assert fmt.refs == 1  # exactly one real call (comment substring ignored)
    # the cross-module call edge is present and resolved
    assert any(e.referenced_name == "format_date" and e.resolved_module == "pkg.dates" for e in edges)
