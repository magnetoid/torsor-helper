---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T12:05:00'
updated: '2026-06-02T12:05:00'
rules: []
---

# ADR 0005: The drift baseline is committed config, not disposable index

## Context
The v0.2 drift baseline grandfathers pre-existing violations so `--strict` fails
only on *new* drift, making the guard adoptable mid-life. A baseline is not
rebuildable — deleting it re-fails every grandfathered violation — so it does not
belong under the disposable `.index/`.

## Decision
Store the baseline at `.torsor/baseline.json` (a committed, reviewable sibling of
the charter), keyed on `(file, rule_kind, target)` with per-tuple counts. No
fuzzy snippet-hash (which could let a genuinely-new violation silently inherit an
old hash). `torsor guard --update-baseline` is the *only* writer; `check_drift`
stays side-effect-free.

## Consequences
The CI ratchet is reviewable in PRs and survives index rebuilds. `--strict` fails
when a tuple's current count exceeds its baseline count. Map fingerprints, by
contrast, *do* live in the rebuildable index — the distinction is whether the
state is source-of-truth (baseline) or derived (fingerprint, vectors, symbols).
