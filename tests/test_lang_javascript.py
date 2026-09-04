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
