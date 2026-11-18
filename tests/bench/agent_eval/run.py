"""Run the ten tasks in tasks.yaml with and without torsor and grade them.

For every (task, arm, repetition) a fresh git worktree of the janus checkout is
made, the arm's configuration is laid in, `claude -p` runs the task headless,
the JSON result (cost, turns, tokens, duration) is kept, the answer or diff is
graded without a model, and the worktree is removed.

    uv run python tests/bench/agent_eval/run.py <janus-checkout> --out results/ [--reps 2]
    uv run python tests/bench/agent_eval/run.py <janus-checkout> --out results/ --only q1 --arms plain
    uv run python tests/bench/agent_eval/run.py --report results/

The torsor arm expects the checkout to carry the `.torsor/`, `.mcp.json` and
`.claude/settings.json` that seed_torsor.py writes; the plain arm gets the same
checkout with those three removed. Both arms see the repo's own CLAUDE.md and
AGENTS.md. Both run with the same model, tool allowlist and turn cap.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ARMS = ("plain", "torsor")
ALLOWED_TOOLS = (
    "Read Edit Write Grep Glob "
    "Bash(git log*) Bash(git show*) Bash(git diff*) Bash(git status*) Bash(git blame*) "
    "Bash(grep *) Bash(rg *) Bash(ls *) Bash(cat *) Bash(head *) Bash(tail *) Bash(sed -n*) Bash(find *) Bash(wc *) "
    "mcp__torsor-helper__*"
)
TORSOR_FILES = (".torsor", ".mcp.json", ".claude/settings.json")
# The arm's setup is not the agent's work: it stays out of the graded diff and
# the saved one. Seeded ADR text quotes the very literals the `rule` tasks
# forbid, so staging it would fail the torsor arm on its own memory.
AGENT_DIFF_PATHSPEC = (".", *(f":(exclude){f}" for f in TORSOR_FILES))


def sh(*args: str, cwd: Path, check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if check and proc.returncode:
        raise SystemExit(f"$ {' '.join(args)}\n{proc.stdout}{proc.stderr}")
    return proc


def make_worktree(checkout: Path, dest: Path, arm: str) -> None:
    sh("git", "worktree", "add", "--detach", str(dest), "HEAD", cwd=checkout)
    for link in (".venv", "node_modules"):
        src = checkout / link
        if src.exists() and not (dest / link).exists():
            (dest / link).symlink_to(src.resolve())
    if arm == "torsor":
        for rel in TORSOR_FILES:
            src, dst = checkout / rel, dest / rel
            if not src.exists():
                raise SystemExit(f"torsor arm needs {src} — run seed_torsor.py first")
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        # `torsor init --write` pins the server to the checkout with an absolute
        # --root; the arm must serve the worktree's own .torsor, not the checkout's.
        mcp = dest / ".mcp.json"
        mcp.write_text(mcp.read_text().replace(str(checkout), str(dest)))
    else:
        for rel in TORSOR_FILES:  # .mcp.json is committed in janus; the plain arm must not see it
            p = dest / rel
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()


def remove_worktree(checkout: Path, dest: Path) -> None:
    for link in (".venv", "node_modules"):
        p = dest / link
        if p.is_symlink():
            p.unlink()
    sh("git", "worktree", "remove", "--force", str(dest), cwd=checkout, check=False)


def parse_stream(lines: list[tuple[float, str]]) -> dict:
    """The final `result` event of a `stream-json` run, plus a trace built from
    the events before it. `lines` are (seconds since start, raw line): the
    stream carries no timestamps of its own, so the reader stamps each line.

    trace.tools  — every tool call in order (name, ms until its result)
    trace.hooks  — every hook run (name, ms, outcome, chars of context it injected)
    Without this a cell says only that one arm cost more, never which tool or
    hook spent it."""
    data: dict = {}
    tools: list[dict] = []
    open_tools: dict[str, dict] = {}
    hooks: list[dict] = []
    open_hooks: dict[str, float] = {}
    for t, raw in lines:
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind, sub = ev.get("type"), ev.get("subtype")
        if kind == "result":
            data = ev
        elif kind == "system" and sub == "hook_started":
            open_hooks[ev.get("hook_id", "")] = t
        elif kind == "system" and sub == "hook_response":
            start = open_hooks.pop(ev.get("hook_id", ""), t)
            context = ""
            try:
                context = json.loads(ev.get("stdout") or "{}").get("hookSpecificOutput", {}).get("additionalContext", "")
            except (json.JSONDecodeError, AttributeError):
                pass
            hooks.append({"hook": ev.get("hook_name"), "ms": round((t - start) * 1000),
                          "outcome": ev.get("outcome"), "context_chars": len(context or "")})
        elif kind in ("assistant", "user"):
            content = (ev.get("message") or {}).get("content")
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_use":
                    call = {"tool": c.get("name"), "ms": None}
                    open_tools[c.get("id", "")] = {"call": call, "t": t}
                    tools.append(call)
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in open_tools:
                    pending = open_tools.pop(c["tool_use_id"])
                    pending["call"]["ms"] = round((t - pending["t"]) * 1000)
    if not data:
        data = {"is_error": True, "result": "\n".join(raw for _, raw in lines[-5:])[-4000:]}
    data["trace"] = {"tools": tools, "hooks": hooks}
    return data


def run_agent(worktree: Path, prompt: str, arm: str, model: str, max_turns: int, timeout: int) -> dict:
    cmd = [
        "claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--include-hook-events",
        "--no-session-persistence",
        "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED_TOOLS,
        "--max-turns", str(max_turns), "--model", model, "--strict-mcp-config",
        # The operator's own plugins, hooks and skills (user settings) stay out of
        # both arms: they add ~9k tokens to every run and their SessionStart hooks
        # steer the agent. Project settings stay — that is where torsor's hooks live.
        "--setting-sources", "project,local",
    ]
    if arm == "torsor":
        cmd += ["--mcp-config", str(worktree / ".mcp.json")]
    else:
        cmd += ["--mcp-config", '{"mcpServers":{}}']
    # The arm's hooks and MCP server spawn a bare `torsor`; it must be the one
    # under test (this interpreter's), not whatever older install is on PATH.
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    t = time.perf_counter()
    lines: list[tuple[float, str]] = []
    with tempfile.TemporaryFile("w+") as err:  # a file, not a pipe: nobody reads stderr while stdout streams
        proc = subprocess.Popen(cmd, cwd=worktree, text=True, stdout=subprocess.PIPE, stderr=err, env=env)
        fired: list[bool] = []
        killer = threading.Timer(timeout, lambda: (fired.append(True), proc.kill()))
        killer.start()
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                lines.append((time.perf_counter() - t, raw))
            proc.wait()
        finally:
            killer.cancel()
        err.seek(0)
        stderr = err.read()[-2000:]
    data = parse_stream(lines)
    if fired:
        data.update(is_error=True, result=f"timeout after {timeout}s")
    data["stderr"] = stderr
    data["wall_s"] = time.perf_counter() - t
    return data


def grade_question(task: dict, answer: str) -> tuple[bool, list[str]]:
    low = answer.lower()
    notes = []
    ok = True
    if "expect_all" in task:
        missing = [s for s in task["expect_all"] if s.lower() not in low]
        if missing:
            ok = False
            notes.append(f"missing all-of: {missing}")
    if "expect_any" in task and not any(s.lower() in low for s in task["expect_any"]):
        ok = False
        notes.append(f"none of: {task['expect_any']}")
    return ok, notes


def agent_diff(worktree: Path, *extra: str) -> str:
    """The agent's own changes: everything in the worktree except the arm's setup files."""
    return sh("git", "diff", "--cached", *extra, "--", *AGENT_DIFF_PATHSPEC, cwd=worktree).stdout


def grade_edit(task: dict, worktree: Path) -> tuple[bool, list[str]]:
    sh("git", "add", "-A", "--", ".", cwd=worktree)
    for rel in TORSOR_FILES:  # unstage the arm's setup; `add` refuses an exclude pathspec that names an ignored path
        sh("git", "reset", "-q", "--", rel, cwd=worktree, check=False)
    diff = agent_diff(worktree, "--unified=0")
    changed = agent_diff(worktree, "--name-only").split()
    added = "\n".join(line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    notes, ok = [], True
    for req in task.get("require", []):
        files = [f for f in changed if fnmatch(f, req["file"])]
        hit = any(re.search(req["regex"], (worktree / f).read_text(encoding="utf-8", errors="replace"))
                  for f in files if (worktree / f).is_file())
        if not hit:
            ok = False
            notes.append(f"require failed: {req['file']} ~ /{req['regex']}/ (changed: {files or 'nothing'})")
    for fb in task.get("forbid", []):
        m = re.search(fb["regex"], added)
        if m:
            ok = False
            notes.append(f"forbidden in added lines: /{fb['regex']}/ -> {m.group(0)!r}")
    if not changed:
        notes.append("no files changed")
    return ok, notes


def run_tests(task: dict, worktree: Path) -> bool | None:
    if not task.get("tests"):
        return None
    proc = sh("scripts/run_tests.sh", *task["tests"], cwd=worktree, check=False, timeout=900)
    return proc.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkout", nargs="?", type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--only", action="append", default=[], help="task id prefix (repeatable)")
    ap.add_argument("--arms", default="plain,torsor")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--run-tests", action="store_true")
    ap.add_argument("--report", type=Path, help="only summarise this results directory")
    args = ap.parse_args()
    if args.report:
        report(args.report)
        return
    if not args.checkout:
        ap.error("checkout is required unless --report")

    tasks = yaml.safe_load((HERE / "tasks.yaml").read_text())
    if args.only:
        tasks = [t for t in tasks if any(t["id"].startswith(p) for p in args.only)]
    arms = [a for a in args.arms.split(",") if a in ARMS]
    checkout = args.checkout.resolve()
    # absolute: `git worktree add` resolves the destination from the checkout,
    # every later open() and cwd= from here — a relative --out split the two
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    scratch = args.out / "worktrees"
    scratch.mkdir(exist_ok=True)

    for rep in range(args.reps):
        for task in tasks:
            for arm in arms:
                name = f"{task['id']}__{arm}__r{rep}"
                out = args.out / f"{name}.json"
                if out.exists() and not json.loads(out.read_text()).get("is_error"):
                    print(f"skip {name} (done)")  # an errored run (auth, timeout) is retried
                    continue
                wt = scratch / name
                if wt.exists():
                    remove_worktree(checkout, wt)
                make_worktree(checkout, wt, arm)
                try:
                    print(f"run  {name} ...", end=" ", flush=True)
                    res = run_agent(wt, task["prompt"], arm, args.model, args.max_turns, args.timeout)
                    answer = res.get("result") or ""
                    if task["kind"] == "question":
                        passed, notes = grade_question(task, answer)
                    else:
                        passed, notes = grade_edit(task, wt)
                        res["diff"] = agent_diff(wt)[:60000]
                        if args.run_tests:
                            res["tests_pass"] = run_tests(task, wt)
                    record = {
                        "task": task["id"], "kind": task["kind"], "claim": task.get("claim"), "arm": arm, "rep": rep,
                        "passed": passed, "notes": notes, "is_error": bool(res.get("is_error")),
                        "cost_usd": res.get("total_cost_usd"), "turns": res.get("num_turns"),
                        "duration_ms": res.get("duration_ms"), "wall_s": res.get("wall_s"),
                        "usage": res.get("usage"), "answer": answer, "diff": res.get("diff"),
                        "stderr": res.get("stderr"), "tests_pass": res.get("tests_pass"),
                        "trace": res.get("trace"),
                    }
                    out.write_text(json.dumps(record, indent=1))
                    print(f"{'PASS' if passed else 'FAIL'}  ${record['cost_usd'] or 0:.2f}  {record['turns']} turns")
                finally:
                    remove_worktree(checkout, wt)
    report(args.out)


def _tokens(u: dict | None) -> int:
    if not u:
        return 0
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                             "cache_read_input_tokens", "output_tokens"))


def report(out: Path) -> None:
    recs = [json.loads(p.read_text()) for p in sorted(out.glob("*.json"))]
    if not recs:
        print("no results")
        return
    print(f"\n{'task':<28} {'arm':<7} {'pass':>5} {'cost $':>7} {'turns':>6} {'tokens':>9} {'wall s':>7}")
    for task in sorted({r["task"] for r in recs}):
        for arm in ARMS:
            rows = [r for r in recs if r["task"] == task and r["arm"] == arm]
            if not rows:
                continue
            passed = sum(r["passed"] for r in rows)
            cost = statistics.mean(r["cost_usd"] or 0 for r in rows)
            turns = statistics.mean(r["turns"] or 0 for r in rows)
            toks = statistics.mean(_tokens(r["usage"]) for r in rows)
            wall = statistics.mean(r["wall_s"] or 0 for r in rows)
            print(f"{task:<28} {arm:<7} {passed:>2}/{len(rows):<2} {cost:>7.2f} {turns:>6.1f} {toks:>9.0f} {wall:>7.0f}")
    print()
    for arm in ARMS:
        rows = [r for r in recs if r["arm"] == arm]
        if not rows:
            continue
        by_claim = {}
        for r in rows:
            by_claim.setdefault(r["claim"], []).append(r["passed"])
        claims = "  ".join(f"{c}: {sum(v)}/{len(v)}" for c, v in sorted(by_claim.items()))
        print(f"{arm:<7} passed {sum(r['passed'] for r in rows)}/{len(rows)}  "
              f"cost ${sum(r['cost_usd'] or 0 for r in rows):.2f}  "
              f"tokens {sum(_tokens(r['usage']) for r in rows):,}  |  {claims}")
    traced = [r for r in recs if r.get("trace")]
    if traced:
        print("\nwhere the time and turns went (runs recorded with a trace)")
        for arm in ARMS:
            rows = [r for r in traced if r["arm"] == arm]
            if not rows:
                continue
            calls = Counter(c["tool"] for r in rows for c in r["trace"]["tools"])
            tool_s = sum((c["ms"] or 0) for r in rows for c in r["trace"]["tools"]) / 1000
            hook_ms: dict[str, list[int]] = {}
            for r in rows:
                for h in r["trace"]["hooks"]:
                    hook_ms.setdefault(h["hook"], []).append(h["ms"])
            hooks = ", ".join(f"{name} x{len(v)} {sum(v) / 1000:.1f}s" for name, v in sorted(hook_ms.items()))
            print(f"{arm:<7} {len(rows)} runs  tool time {tool_s:.0f}s  hooks: {hooks or 'none'}")
            print("        calls: " + (", ".join(f"{name} {n}" for name, n in calls.most_common()) or "none"))
    errors = [r for r in recs if r["is_error"]]
    if errors:
        print(f"\n{len(errors)} run(s) errored: " + ", ".join(f"{r['task']}/{r['arm']}" for r in errors))


if __name__ == "__main__":
    main()
