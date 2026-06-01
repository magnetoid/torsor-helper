from torsor_helper.cartographer import render_map
from torsor_helper.models import Symbol


def _syms():
    return [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="pkg/dates.py", line=1, doc="Format.", refs=3),
        Symbol(name="Cartographer", kind="class", signature="Cartographer", module="pkg/cart.py", line=1, doc="Maps.", refs=1),
        Symbol(name="Cartographer.mapit", kind="method", signature="mapit(self, root)", module="pkg/cart.py", line=3, refs=0),
    ]


def test_render_map_overview_and_modules():
    out = render_map(_syms())
    assert "overview.md" in out
    title, body = out["overview.md"]
    assert title == "Repository Map"
    assert "pkg/dates.py" in body and "pkg/cart.py" in body
    assert "modules/pkg__dates.py.md" in out
    mod_title, mod_body = out["modules/pkg__cart.py.md"]
    assert mod_title == "pkg/cart.py"
    assert "mapit(self, root)" in mod_body
    assert "L3" in mod_body


def test_render_map_empty():
    out = render_map([])
    assert "overview.md" in out
    assert out["overview.md"][0] == "Repository Map"
