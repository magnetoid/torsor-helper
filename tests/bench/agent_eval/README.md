# Does torsor help the agent? A measurement, not an opinion

torsor's central claim is that an agent with committed memory, an enforcing
guard and a code map does better work for fewer tokens than the same agent
with only the repo's own `CLAUDE.md`/`AGENTS.md`. Until this harness existed
nobody had measured it. This runs the same headless agent (`claude -p`) over
the same ten tasks on a real 5 000-file repository (janus), once per arm, and
grades every result without a model.

## Arms

| arm | gets |
|---|---|
| `plain` | the janus checkout as it is: `CLAUDE.md`, `AGENTS.md`, git history. No MCP servers, no hooks. |
| `torsor` | the same, plus `.torsor/` (charter, active context, a journal built from the last 20 commits, three ADRs with guard rules transcribed from AGENTS.md "Known Pitfalls", the code map), the torsor MCP server, and the SessionStart + PreToolUse hooks. The guard runs in torsor's default `advise` mode: the hook shows the finding, the agent decides. `seed_torsor.py --guard-mode block` seeds an arm where the hook denies the edit instead (ADR 0012); the rules carry `severity: error` so that mode bites. |

Same model, same tool allowlist, same turn cap, fresh git worktree per run.
The three ADR rules encode prose that is **already in AGENTS.md for both
arms**; the difference under test is enforcement on edit, not knowledge.

## Tasks (`tasks.yaml`)

Five questions and five edits, each tagged with the claim it tests:

- `orientation` (q1, q2, q5): facts in the repo both arms can grep. Measures tokens and turns to a correct answer, not whether one arm can answer at all.
- `memory` (q3, q4): facts in git history / recorded state. The plain arm can reach them through `git log`; the torsor arm through recall and the active context. q4 is the one task where the plain arm has no sure source, and the grader accepts "nothing recorded" as a fail, deliberately: that is the memory claim.
- `convention` (e1, e4, e5): edits that must follow a repo convention (command registry, tool registration + toolset, config defaults). Graded by regexes over the changed files.
- `rule` (e2, e3): edits that tempt a Known Pitfall (hardcoded `~/.janus`, `\033[K`). Graded by regexes over the diff's added lines. This is where the guard hook can fire. The graded diff is the agent's work only: the arm's setup (`.torsor/`, `.mcp.json`, `.claude/settings.json`) is excluded, since the seeded ADR text quotes the very literals these tasks forbid.

Graders are substrings and regexes, so a run can pass on wording luck or fail
on phrasing; read the saved answers and diffs before trusting a single cell.
Repetitions (`--reps`) matter more than task count.

## Running

```bash
# 1. a janus checkout with .venv (symlinked is fine); seed the torsor arm from real material.
#    An existing .torsor/ is kept as .torsor.real and used as the source of charter + active context.
uv run python tests/bench/agent_eval/seed_torsor.py /path/to/janus            # advisory guard (torsor's default)
uv run python tests/bench/agent_eval/seed_torsor.py /path/to/janus --guard-mode block

# 2. the headless CLI must be logged in (claude login) — the harness never handles credentials
claude -p "ok" --max-turns 1 --output-format json | head -c 200

# 3. pilot one task, both arms, then the full matrix
uv run python tests/bench/agent_eval/run.py /path/to/janus --out /tmp/eval --only q1
uv run python tests/bench/agent_eval/run.py /path/to/janus --out /tmp/eval --reps 2

# 4. the table again, any time
uv run python tests/bench/agent_eval/run.py --report /tmp/eval
```

Each run writes one JSON record (grade, notes, cost, turns, tokens, wall time,
the answer, the diff) so a cell can be re-read later. Finished runs are
skipped on rerun, so a stopped matrix resumes.

## Reading the result

- A torsor win is: more passes on `rule` and `memory`, at equal or lower cost on `orientation`.
- A torsor loss is: more tokens on `orientation` (the MCP tool list and SessionStart digest are not free) with no gain elsewhere. That would mean the fifteen tools are still too many, or the digest too long.
- Cost per run on janus with Sonnet is in the low tens of cents for questions and up to a dollar or two for edits; a 2-rep matrix is 40 runs. Decide the budget before starting it.
