import pytest

pytest.importorskip("tree_sitter")

from torsor_helper.cartographer import compute_refs, scan_repo_with_edges  # noqa: E402
from torsor_helper.languages import go  # noqa: E402

STORE = """\
package svc

import (
\t"fmt"
\t"example.com/app/util"
)

// Store keeps things.
type Store struct{}

// Get fetches one.
func (s *Store) Get(id int) int { return util.Norm(id) }

func New() *Store { fmt.Println("x"); return &Store{} }
"""


def test_go_definitions():
    syms = {s.name: s for s in go.extract(STORE, "svc/store.go")[0]}
    assert syms["Store"].kind == "type" and syms["Store"].doc == "Store keeps things."
    assert syms["Store.Get"].kind == "method" and syms["Store.Get"].signature == "Get(id int)"
    assert syms["New"].kind == "function" and syms["New"].line == 14


def test_go_edges_and_hints():
    edges = go.extract(STORE, "svc/store.go")[1]
    println = next(e for e in edges if e.referenced_name == "Println")
    assert println.resolved_module is None and println.hint == "fmt"
    norm = next(e for e in edges if e.referenced_name == "Norm")
    assert norm.caller == "Store.Get" and norm.hint == "example.com/app/util"
    store_call = next(e for e in edges if e.referenced_name == "Store" and e.role == "call")
    assert store_call.resolved_module == "svc.store"  # same file


def test_same_package_and_repo_package_calls_resolve_via_compute_refs(tmp_path):
    (tmp_path / "svc").mkdir()
    (tmp_path / "util").mkdir()
    (tmp_path / "svc" / "store.go").write_text(STORE)
    (tmp_path / "svc" / "other.go").write_text("package svc\n\nfunc Use() int { return New().Get(1) }\n")
    (tmp_path / "util" / "norm.go").write_text("package util\n\nfunc Norm(n int) int { return n }\n")
    symbols, edges = scan_repo_with_edges(tmp_path)
    new = next(e for e in edges if e.referenced_name == "New" and e.module == "svc/other.go")
    assert new.resolved_module == "svc.store"           # same package, other file
    norm = next(e for e in edges if e.referenced_name == "Norm")
    assert norm.resolved_module == "util.norm"           # import path tail → repo dir
    refs = {s.name: s.refs for s in symbols}
    assert refs["New"] == 1 and refs["Norm"] == 1 and refs["Store.Get"] == 0
    compute_refs(symbols, edges)                            # idempotent
    assert {s.name: s.refs for s in symbols} == refs
