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
import re
import shutil
import statistics
import subprocess
import time
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


def run_agent(worktree: Path, prompt: str, arm: str, model: str, max_turns: int, timeout: int) -> dict:
    cmd = [
        "claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
        "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED_TOOLS,
        "--max-turns", str(max_turns), "--model", model, "--strict-mcp-config",
    ]
    if arm == "torsor":
        cmd += ["--mcp-config", str(worktree / ".mcp.json")]
    else:
        cmd += ["--mcp-config", '{"mcpServers":{}}']
    t = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=worktree, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {"is_error": True, "result": f"timeout after {timeout}s", "stderr": str(exc.stderr)[-2000:],
                "wall_s": time.perf_counter() - t}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"is_error": True, "result": proc.stdout[-4000:]}
    data["stderr"] = proc.stderr[-2000:]
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


def grade_edit(task: dict, worktree: Path) -> tuple[bool, list[str]]:
    sh("git", "add", "-A", cwd=worktree)
    diff = sh("git", "diff", "--cached", "--unified=0", cwd=worktree).stdout
    changed = sh("git", "diff", "--cached", "--name-only", cwd=worktree).stdout.split()
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
                        res["diff"] = sh("git", "diff", "--cached", cwd=wt).stdout[:60000]
                        if args.run_tests:
                            res["tests_pass"] = run_tests(task, wt)
                    record = {
                        "task": task["id"], "kind": task["kind"], "claim": task.get("claim"), "arm": arm, "rep": rep,
                        "passed": passed, "notes": notes, "is_error": bool(res.get("is_error")),
                        "cost_usd": res.get("total_cost_usd"), "turns": res.get("num_turns"),
                        "duration_ms": res.get("duration_ms"), "wall_s": res.get("wall_s"),
                        "usage": res.get("usage"), "answer": answer, "diff": res.get("diff"),
                        "stderr": res.get("stderr"), "tests_pass": res.get("tests_pass"),
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
    errors = [r for r in recs if r["is_error"]]
    if errors:
        print(f"\n{len(errors)} run(s) errored: " + ", ".join(f"{r['task']}/{r['arm']}" for r in errors))


if __name__ == "__main__":
    main()
