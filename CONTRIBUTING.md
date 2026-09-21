# Contributing

```bash
uv run --extra dev pytest -q -n auto           # the suite (~45s parallel)
uv run --extra dev --extra languages pytest -q # with the JS/TS/Go extractors
uv run --extra dev ruff check src tests        # exactly what CI runs
uv run torsor guard --strict $(git ls-files '*.py')
```

`pre-commit install` wires the first, third and fourth into your commits.

## What the reviewer will look for

**A failing test first.** The convention here is genuine TDD: write the test,
watch it fail for the reason you expect, then make it pass. Several bugs in
this codebase were found because a test written to describe intended behaviour
failed for an unexpected reason.

**Measure before you optimize, reproduce before you fix.** The performance pass
found that the two most expensive operations were syscall-per-note bugs that no
audit had predicted, and several "findings" turned out not to be real once
someone built the case. A commit message that claims an improvement should
carry the number.

**Say what you did not do.** A commit that fixes three of four things and names
the fourth is worth more than one that quietly leaves it.

## Things that are easy to break without noticing

- **A guard scope that matches nothing reports nothing**, which reads exactly
  like a rule that passes. After changing a `scope:`, feed the rule a
  deliberate violation and check it still fires.
- **`torsor guard` with no arguments checks git-changed files**, so on a clean
  tree it checks nothing. Always pass the file list in CI.
- **`norm_path` is for file paths, `norm_module` for possibly-dotted keys.**
  Picking the wrong one silently empties the reference graph.
- **Submodules of `operations/` import siblings by full path**, never the
  package façade (ADR 0014).
- **A schema change must bump `SCHEMA_VERSION`**; `db.connect` trusts the stamp.
- **Every context-returning path is token-budgeted**, and the budget covers what
  actually lands in context.

`CLAUDE.md` is the long form of all of this.

## Architecture decisions

Load-bearing structural choices get an ADR in `.torsor/architecture/decisions/`,
with a machine-readable `rules:` block where the decision can be checked. Then
`torsor rules --scoped` so agents working in the repo see it.
