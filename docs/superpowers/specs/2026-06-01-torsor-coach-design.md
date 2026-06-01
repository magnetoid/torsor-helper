# torsor-helper Coach — Design Spec

**Date:** 2026-06-01
**Status:** Approved (brainstorming) → roadmap **Phase 6**, built after Phases 2–4
**Parent design:** [`2026-06-01-torsor-helper-design.md`](2026-06-01-torsor-helper-design.md)
**Repo:** https://github.com/magnetoid/torsor-helper

## 1. Problem

Phase 1–4 make torsor-helper a good *memory*. But a second brain only works if it's *maintained* and if its accumulated knowledge actually changes behavior. Two gaps remain:

1. **Knowledge rots silently.** The wiki goes stale, the architecture doc stays a placeholder, decisions pile up with no rules — and nobody notices until a session collapses again. Nothing watches the *health* of the pyramid.
2. **Learnings are passive.** Memory only helps if the agent happens to `recall` the right thing. The high-ROI move — telling the agent "this already exists / you decided this / this was rejected" *before* it reimplements — never fires on its own.

The **Coach** closes both. It is an **independent, non-intrusive advisor**: it observes the `.torsor/` pyramid and the codebase over time and emits **recommendations** — both to keep the knowledge base healthy and to steer coding toward best practices. It never edits code and never blocks an edit. Think *project doctor*, running beside the work, not inside it.

This directly addresses documented vibe-coding failure modes beyond the original three: **code duplication** (giving the agent an "existing utility inventory" cuts duplication 60–70%), **inconsistent patterns**, **lost architectural intent**, **re-introduction of rejected approaches**, and **repeat bugs / happy-path bias**. Security and dependency scanning are explicitly out of scope (better served by integrating dedicated tools — see §10).

## 2. Decisions (from brainstorming)

1. **Scope:** learnings **+** codebase (anti-duplication, consistency) **+** knowledge-hygiene/maturity. Not security/dependency scanning.
2. **Delivery:** woven into existing tool outputs **+** a dedicated `recommend()` tool **+** an out-of-band `torsor coach` report (the *primary* surface).
3. **Learnings:** explicit (`remember(kind=learning)`, ADRs) **+** auto-mined from history.
4. **Architecture A — retrieval-based recommender:** a thin actionable lens over the Phase-2 index + Phase-3 map; deterministic; every recommendation cites its source. Borrow the map's symbol inventory for instant anti-duplication; sampling-based phrasing is an optional later enhancement, not core.
5. **Stance:** external, observational, advisory-only — never writes code, never blocks. Runs out of the coding hot-path.
6. **Sequencing:** built as **Phase 6**, after the index (Phase 2), map (Phase 3), and guard (Phase 4) exist. Earlier phases leave the hooks in §8.

## 3. The recommendation model

```
recommend(context, *, kinds=None, limit=5) -> Recommendations
```

`Recommendation`: `kind`, `severity` (info | suggest | important), `message`, `evidence`, `source_path` + `citation`, `action` (a concrete next step), `score`, `key` (stable id for dedup/decay).
`Recommendations`: `context`, `items: list[Recommendation]`, `total_tokens`.

Every recommendation carries its **evidence + a concrete action + a source citation** — it is auditable, never a black box.

### Two families of recommendation

**A. Knowledge hygiene & maturity** — is the second brain being maintained? (Deterministic checks over project state; need only the filesystem + git, so they work from day one.)

| Kind | Fires when | Evidence | Suggested action |
|---|---|---|---|
| `stale` | a tier file lags code changes | `updated`/mtime vs. recent source commits | "Active context is 6 sessions old — run `handoff` / `update_active`" |
| `thin` | charter/system-patterns/tech-context still seed-template or has empty sections | diff vs. `templates.py`; unfilled `_placeholder_` sections | "Architecture is still a placeholder — clarify §Conventions" |
| `unruled` | many decisions, ~0 machine-readable rules/ADRs | count(decisions) vs. count(`rules:`) | "12 decisions, 0 rules — formalize the load-bearing ones as ADRs" |
| `uncharted` | code modules with no `map/` entry | repo module set − mapped set | "`payments/` isn't mapped — run `torsor map`" |

**B. Coding best-practices** — the problems we set out to solve, delivered as nudges (never enforcement). Retrieval-based.

| Kind | Sourced from | Targets |
|---|---|---|
| `reuse` | Phase-3 symbol inventory | code duplication (≈8×) |
| `convention` | `system-patterns.md` + ADR `rules:` | inconsistent patterns |
| `decision` | ADRs / `decision` memory | lost architectural intent |
| `rejection` | `rejection` insight notes | re-introducing rejected code |
| `learning` | `learning`/`blocker` notes | repeat bugs / happy-path bias |

## 4. Components

```
src/torsor_helper/coach/
  models.py        # RecommendationKind, Severity, Recommendation, Recommendations
  health.py        # deterministic hygiene checks (stale/thin/unruled/uncharted) -> list[Recommendation]
  recommender.py   # recommend(): retrieval-based best-practice recs (reuse/convention/decision/rejection/learning)
  mining.py        # mine_insights(): materialize derived insight notes from history (consolidate-time)
  state.py         # CoachState: dismissal/decay/escalation tracking (derived, disposable)
  report.py        # assemble + rank + budget a checkup report from both families
```

- `health.py` is pure functions over `Store` + repo state — no index/embeddings required.
- `recommender.py` reuses the Phase-2 retriever (filtered to actionable `type`/`kind`) and the Phase-3 symbol inventory.
- All recommendation logic lives here; `server.py`/`cli.py` stay thin adapters.

## 5. Data flow

**Anti-duplication (the money example):**
> Agent calls `recommend("add a date formatter")` → retrieve symbol-map hits for "date/format" (`reuse`), date conventions (`convention`), prior decisions (`decision`) → rank → return:
> *"♻️ Reuse `format_date()` — `utils/dates.py:12` · convention: ISO-8601 only (system-patterns) · ADR-009 chose `dayjs`."* — each line links to its source.

**Checkup (the primary surface):**
> `torsor coach` → run all hygiene checks + top best-practice recs for the active focus → rank by severity × relevance → print a prioritized report with evidence + actions. Exit 0 (advisory) unless `--strict`.

**Maintenance:** `torsor consolidate` runs `mine_insights`, refreshing derived insight notes that feed family B.

## 6. Surfaces (out of the coding hot-path)

- **`torsor coach`** — prioritized checkup report. The primary, independent surface.
- **`bootstrap_session`** — a short, budgeted "## Recommendations" digest (top 3 above threshold, dismissible). Gentle, not blocking.
- **`recommend(context?, kinds?, limit?)`** — MCP tool the agent pulls on demand.
- (Phase 4) `check_drift` / `get_intent` outputs include the relevant `convention`/`decision` recs.

## 7. Stabilisation over time (noise & decay control)

Derived, git-ignored `.torsor/.index/coach_state.json` tracks per-`key`: `first_seen`, `times_shown`, `last_shown`, `dismissed`, `resolved`.

- **Escalate:** a persistent unresolved hygiene issue raises severity slowly ("architecture still unclear — 4th checkup").
- **Decay:** an ignored-but-not-dismissed rec drops in rank after K shows.
- **Dismiss:** `recommend --dismiss <key>` / `torsor coach --dismiss <key>` suppresses a rec until its evidence materially changes.
- **Auto-clear:** when the evidence is gone (file updated, rule added, module mapped), the rec resolves itself.

State is disposable and rebuildable — consistent with "Markdown is the source of truth; the index is derived."

## 8. Hooks earlier phases must leave (actionable output of this spec)

- **Phase 2 (index):** retrieval filterable by frontmatter `type`/`kind`; index stores `type`, `kind`, `signal_strength`; track per-note access frequency (feeds signal strength); add the `memory/insights/` path to the layout; register a thin `recommend` MCP tool **stub** that returns hygiene-only recommendations until Phase 6 fills it in.
- **Phase 3 (map):** expose a queryable **symbol inventory** (name, signature, file, summary) for `reuse`, and the repo module list for `uncharted`.
- **Phase 4 (guard):** emit consistency findings in a shape the Coach surfaces as `convention` recs; ADR `rules:` frontmatter is the shared rules source for `unruled` and consistency.
- **Layout (now):** add the `memory/insights/` tier (derived notes, committed — human-readable).

## 9. Error handling / degradation

- **No index/map yet** → Coach runs **hygiene checks only** (filesystem + git) plus learnings via keyword recall. Family B lights up as Phases 2–3 land.
- A malformed note/insight is **skipped and logged**, never fatal to a checkup.
- `coach_state.json` corrupt → reset (it's derived).
- A checkup **never exits non-zero** unless `--strict`. The Coach never blocks coding.

## 10. Out of scope (YAGNI / better served elsewhere)

- **Security scanning** (hardcoded secrets, SQLi, broken access control) and **dependency/slopsquatting checks** — real problems, but better served by *integrating* dedicated tools (gitleaks, semgrep, OSV/Snyk) than reimplementing them. A future `convention`/`integration` rec could *point to* running them; the Coach does not scan.
- **Learned ranking / ML models** — v1 ranking is heuristic (relevance × signal × type weight).
- **Auto-editing the wiki or code** — the Coach only recommends; the human/agent acts.
- **Real-time watching** — checkups are on-demand (`torsor coach`) or at session start; a live watcher is a later optimization.

## 11. Testing strategy (TDD)

- **Hygiene checks** — fixture projects: fresh seed → all `thin`; edited-but-stale docs + recent code → `stale`; decisions-without-rules → `unruled`; an unmapped module → `uncharted`. Deterministic, no embeddings.
- **Mining** — fixture journal/decisions → expected idempotent insight notes (re-run = no duplicates).
- **Best-practice recs** — fake embedder + seeded insights/symbols → expected ranked recs, each with a citation.
- **Noise/decay** — dismissed keys suppressed; persistence escalates severity; resolved evidence clears; bootstrap digest capped at top-3.
- **CLI** — `torsor coach` on a scaffolded project prints a prioritized report and exits 0.

## 12. Success criteria

- Running `torsor coach` on a real, partly-maintained project surfaces accurate, actionable hygiene nudges (stale/thin/unruled/uncharted) with evidence.
- `recommend("add X")` returns a `reuse` rec when `X` already exists, citing the symbol — demonstrating the anti-duplication loop.
- Recommendations the user dismisses do not reappear; unresolved ones escalate; resolved ones disappear — demonstrating non-nagging stabilisation over time.
