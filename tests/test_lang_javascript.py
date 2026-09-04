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
