from torsor_helper.cartographer import extract_symbols


SRC = '''"""Module."""
import os


def format_date(d, fmt="iso"):
    "Format a date."
    return d


class Cartographer:
    """Maps a repo."""

    def mapit(self, root):
        return root

    async def scan(self, paths=None):
        pass
'''


def test_extract_functions_classes_methods():
    syms = extract_symbols(SRC, "pkg/mod.py")
    by_name = {s.name: s for s in syms}
    assert by_name["format_date"].kind == "function"
    assert by_name["format_date"].signature == "format_date(d, fmt='iso')"
    assert by_name["format_date"].doc == "Format a date."
    assert by_name["Cartographer"].kind == "class"
    assert by_name["Cartographer.mapit"].kind == "method"
    assert by_name["Cartographer.scan"].kind == "method"
    assert all(s.module == "pkg/mod.py" for s in syms)
    assert by_name["format_date"].line == 5


def test_extract_returns_empty_on_syntax_error():
    assert extract_symbols("def broken(:\n", "x.py") == []
