import pytest

pytest.importorskip("tree_sitter")

from torsor_helper.languages import javascript as js  # noqa: E402

TS = """\
import { format } from './dates';
/** Greets someone. */
export function greet(name: string): string { return format(name); }
export const helper = (x: number) => greet(String(x));
export class Widget extends Base {
  // Renders it.
  render() { return greet('x'); }
}
export interface Props { a: number }
export type Id = string;
"""


def _symbols(text, module="app.ts"):
    return {s.name: s for s in js.extract(text, module)[0]}


def test_typescript_definitions():
    syms = _symbols(TS)
    assert syms["greet"].kind == "function" and syms["greet"].line == 3
    assert syms["greet"].signature == "greet(name: string)"
    assert syms["greet"].doc == "Greets someone."
    assert syms["helper"].kind == "function" and syms["helper"].signature == "helper(x: number)"
    assert syms["Widget"].kind == "class"
    assert syms["Widget.render"].kind == "method" and syms["Widget.render"].doc == "Renders it."
    assert syms["Props"].kind == "type" and syms["Id"].kind == "type"


def test_javascript_and_tsx_grammars_are_selected_by_suffix():
    js_syms = _symbols("function run() {}\nclass Svc {}\n", "a.js")
    assert js_syms["run"].kind == "function" and js_syms["Svc"].kind == "class"
    tsx = _symbols("export const App = () => <div/>;\nexport default function Page() { return <App/>; }\n", "p.tsx")
    assert tsx["App"].kind == "function" and tsx["Page"].kind == "function"


def test_syntax_errors_degrade_to_what_parses():
    assert "ok" in _symbols("function ok() {}\nfunction {{{ broken\n")


def test_nested_and_object_literal_definitions_are_excluded():
    src = """\
function outer() {
  function inner() {}
  const helper = () => 1;
  return inner() + helper();
}
const obj = { foo() { return 1; } };
"""
    syms = _symbols(src, "app.js")
    assert set(syms) == {"outer"}
    assert "inner" not in syms and "helper" not in syms and "foo" not in syms


def test_export_default_class_and_function_are_still_symbols():
    syms = _symbols("export default function Page() { return 1; }\n", "p.ts")
    assert syms["Page"].kind == "function"
    syms2 = _symbols("export default class Widget {}\n", "w.ts")
    assert syms2["Widget"].kind == "class"


def test_class_field_arrow_method_is_a_symbol():
    src = """\
export class Widget {
  // Handles a click.
  onClick = (e) => { return e; };
}
"""
    syms = _symbols(src, "w.ts")
    assert syms["Widget.onClick"].kind == "method"
    assert syms["Widget.onClick"].signature == "onClick(e)"
    assert syms["Widget.onClick"].doc == "Handles a click."

    js_syms = _symbols("class Widget {\n  onClick = (e) => { return e; };\n}\n", "w.js")
    assert js_syms["Widget.onClick"].kind == "method"


def _edges(text, module="app.ts"):
    return js.extract(text, module)[1]


def test_calls_are_attributed_to_their_enclosing_symbol():
    edges = _edges(TS)
    assert any(e.caller == "greet" and e.referenced_name == "format" and e.role == "call" for e in edges)
    assert any(e.caller == "helper" and e.referenced_name == "greet" for e in edges)
    assert any(e.caller == "Widget.render" and e.referenced_name == "greet" for e in edges)


def test_same_file_and_relative_imports_resolve_bare_does_not():
    edges = {(e.referenced_name, e.resolved_module) for e in _edges(
        "import { a } from './lib/a';\nimport React from 'react';\nimport './pkg';\n"
        "function f() { a(); React.x(); g(); }\nfunction g() {}\n", "src/app.ts")}
    assert ("a", "lib.a") in edges          # relative import → module key
    assert ("g", "app") in edges            # same file → own key (src/ stripped)
    assert not any(name == "x" and mod for name, mod in edges)  # bare package stays unresolved


def test_new_and_extends_are_edges():
    edges = _edges("import Base from '../base';\nclass S extends Base { m() { return new Base(); } }\n", "x/s.ts")
    assert any(e.referenced_name == "Base" and e.role == "read" and e.resolved_module == "base" for e in edges)
    assert any(e.referenced_name == "Base" and e.role == "call" and e.caller == "S.m" for e in edges)


def test_require_binds_like_an_import():
    edges = _edges("const h = require('./helper');\nfunction r() { h(); }\n", "a.js")
    assert any(e.referenced_name == "h" and e.resolved_module == "helper" for e in edges)


def test_resolve_relative_collapses_index_and_rejects_escapes():
    assert js.resolve_relative("./pkg", "src/app.ts") == "pkg"
    assert js.resolve_relative("../x/y.js", "src/a/b.ts") == "x.y"
    assert js.resolve_relative("../../escape", "a.ts") is None
    assert js.resolve_relative("lodash", "a.ts") is None


def test_call_inside_nested_helper_is_attributed_to_outer_function():
    edges = _edges(
        "function run() {\n"
        "  function helper() { return util(); }\n"
        "  return helper();\n"
        "}\n", "app.ts")
    assert any(e.caller == "run" and e.referenced_name == "util" for e in edges)
    assert not any(e.caller == "helper" for e in edges)


def test_nested_local_shadowing_a_top_level_import_does_not_win_resolution():
    # R8: a nested local `thing` (inside run()) must not make `top_defs` think
    # the file defines `thing` at top level — foo's reference should still
    # resolve through the `./lib` import, not the file's own module.
    edges = _edges(
        "import { thing } from './lib';\n"
        "function run() { function thing() {} return thing(); }\n"
        "function foo() { return thing(); }\n", "app.ts")
    foo_edge = next(e for e in edges if e.caller == "foo" and e.referenced_name == "thing")
    assert foo_edge.resolved_module == "lib"


def test_class_field_arrow_owner_is_class_dot_field():
    # R9: a reference inside a class-field arrow (`onClick = (e) => {...}`) is
    # attributed to `Class.field`, matching the symbol Task 2 already names it.
    src = "export class Widget {\n  onClick = (e) => { return helper(); };\n}\n"
    edges = _edges(src, "w.ts")
    assert any(e.caller == "Widget.onClick" and e.referenced_name == "helper" for e in edges)

    js_edges = _edges("class Widget {\n  onClick = (e) => { return helper(); };\n}\n", "w.js")
    assert any(e.caller == "Widget.onClick" and e.referenced_name == "helper" for e in js_edges)


def test_this_method_and_reexport_do_not_error():
    # Spot-check: neither construct is resolvable by this best-effort resolver,
    # but neither should raise or produce a bogus resolved edge.
    edges = _edges(
        "export { a } from './b';\nclass C { m() { return this.other(); } }\n", "c.ts")
    assert not any(e.referenced_name == "other" and e.resolved_module for e in edges)
    assert not any(e.referenced_name == "a" for e in edges)


def test_imports_only_treats_require_calls_as_specifiers():
    # A single-string call argument is not an import — `t('hello.world')` was
    # reported as a specifier, inventing a phantom dependency.
    out = js.imports("const g = t('hello.world');\nconst x = require('./x');\n", "a.ts")
    assert out == [("./x", 2)]


def test_imports_are_sorted_by_line_then_specifier():
    src = "import b from './b';\nimport a from './a';\n"
    assert js.imports(src, "a.ts") == [("./b", 1), ("./a", 2)]
    same_line = "import {a} from './z'; import {b} from './y';\n"
    assert js.imports(same_line, "a.ts") == [("./y", 1), ("./z", 1)]
