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
    assert by[("b", "a", "call")].resolved_module == "mod"  # canonical dotted form
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


def test_extract_edges_resolves_relative_imports():
    src = "from .dates import format_date\n\ndef run():\n    return format_date(1)\n"
    edges = extract_edges(src, "pkg/x.py")
    call = next(e for e in edges if e.referenced_name == "format_date" and e.role == "call")
    assert call.resolved_module == "pkg.dates"


def test_extract_edges_from_dot_import_never_yields_empty_module():
    src = "from . import util\n\ndef run():\n    return util.helper()\n"
    edges = extract_edges(src, "pkg/x.py")
    call = next(e for e in edges if e.referenced_name == "helper" and e.role == "call")
    assert call.resolved_module == "pkg"  # the resolved package — never ""


def test_extract_edges_dotted_import_binds_top_name():
    # `import pkg.dates` binds the name `pkg`, so `pkg.f()` resolves to pkg, not pkg.dates
    src = "import pkg.dates\n\ndef run():\n    return pkg.f()\n"
    edges = extract_edges(src, "app.py")
    call = next(e for e in edges if e.referenced_name == "f" and e.role == "call")
    assert call.resolved_module == "pkg"


def test_extract_edges_covers_class_bases_and_decorators():
    src = (
        "class Base:\n    pass\n\n"
        "def deco(c):\n    return c\n\n"
        "@deco\nclass Foo(Base):\n    pass\n"
    )
    edges = extract_edges(src, "mod.py")
    assert any(e.referenced_name == "Base" and e.caller == "Foo" for e in edges)
    assert any(e.referenced_name == "deco" and e.caller == "Foo" for e in edges)


def test_same_module_resolution_is_normalized_dotted():
    # resolved_module must be one canonical dotted form so consumers
    # (who_references / impact) need no per-consumer re-normalization
    src = "def a():\n    pass\n\ndef b():\n    a()\n"
    edges = extract_edges(src, "src/pkg/x.py")
    call = next(e for e in edges if e.referenced_name == "a" and e.role == "call")
    assert call.resolved_module == "pkg.x"


def test_refs_do_not_conflate_methods_with_same_named_functions(tmp_path):
    (tmp_path / "m.py").write_text(
        "def save():\n    pass\n\nclass Store:\n    def save(self):\n        pass\n\n"
        "def run():\n    save()\n"
    )
    syms, _ = scan_repo_with_edges(tmp_path)
    by = {s.name: s for s in syms}
    assert by["save"].refs == 1
    assert by["Store.save"].refs == 0  # methods score 0 by design (ADR 0004)
