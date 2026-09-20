---
type: decision
status: accepted
tags:
- adr
links:
- 0002-adapters-depend-on-core-never-the-reverse
created: '2026-09-20T17:00:00'
updated: '2026-09-20T17:00:00'
rules:
- kind: forbid_pattern
  target: ^from torsor_helper\.operations import
  scope: src/torsor_helper/operations/*.py
  severity: error
  message: "a submodule must import siblings by full path (from torsor_helper.operations.memory import x), never the package facade (ADR 0014) — the facade is half-initialised while the package is loading"
- kind: forbid_pattern
  target: ^from \. import
  scope: src/torsor_helper/operations/*.py
  severity: error
  message: "same as above (ADR 0014): `from . import x` inside operations/ re-enters the package facade during init"
---

# ADR 0014: Inside the operations package, submodules import siblings by path, never the façade

## Context
`operations.py` had grown to ~1500 lines and a dozen unrelated concerns, and the
Coach flagged it as the repo's top hotspot (churn × complexity). Splitting it into
a package is a pure refactor *provided* the adapters and the 34 test modules that
`from torsor_helper import operations as ops` keep working — so `operations/__init__.py`
stays a re-export façade.

That façade creates exactly one new failure mode. While Python is executing
`operations/__init__.py`, the module object exists but is only partly populated.
A submodule that does `from torsor_helper.operations import _log_op` during that
window gets an ImportError or, worse, a name that is silently absent later. It
depends on import order, so it can pass under pytest and fail for a user.

## Decision
Submodules import each other by full path (`from torsor_helper.operations.commands
import list_commands`). The façade itself imports submodules; nothing imports the
façade from inside the package. The two `forbid_pattern` rules above make that
machine-checked rather than a convention, and a test imports every submodule cold,
in isolation, so the ordering hazard cannot hide behind pytest's import order.

## Consequences
- The dependency direction inside the package is explicit and acyclic, and the
  guard says so on every run.
- `monkeypatch` on the façade no longer intercepts calls a submodule makes to a
  sibling. No test relies on that today; the façade docstring says so.
- Adding a concern means adding a module and one re-export line, not growing a file.
