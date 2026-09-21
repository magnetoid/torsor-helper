"""Every deterministic check, and the two hook gates built on them.

guard (declared architectural intent), deps (phantom imports) and staleness
compose into one machine-checkable verdict. The gates that consume it are
advisory by default and never edit code: pre_push can block only when the user
opted in, and pre_edit blocks only on new severity=error drift (ADR 0012)."""
from __future__ import annotations

from pathlib import Path

from torsor_helper import baseline as _baseline
from torsor_helper import deps as _deps
from torsor_helper import gitinfo, guard
from torsor_helper.budget import cap_items
from torsor_helper.operations._shared import _log_op
from torsor_helper.operations.commands import list_commands, run_command
from torsor_helper.operations.maintenance import check_staleness


def check_drift(store, config, files=None) -> list:
    _log_op(store, "check_drift", "")
    if files is None:
        files = gitinfo.changed_source_files(store.paths.root)
    return guard.check_drift(store, files)

def new_drift(store, config, files=None) -> list:
    """Drift beyond the committed baseline — the genuinely-new violations."""
    violations = check_drift(store, config, files)
    return _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))

def guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None) -> dict:
    """The single guard orchestration both adapters share: check drift, apply
    the baseline ratchet, and decide strict failure — so the MCP tool and the
    CLI command can't diverge in behavior."""
    violations = check_drift(store, config, files)
    # A cycle is a property of the whole import graph, so it cannot come out of
    # the per-file pass — it is evaluated once, here, where the store is in hand.
    violations = violations + guard.check_cycles(store, guard.load_rules(store))
    if update_baseline:
        _baseline.save(store.paths.baseline_file, violations)
        return {"violations": violations, "new": [], "baselined": len(violations),
                "failed": False, "updated_baseline": True}
    new = _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))
    failed = bool(strict and guard.strict_failures(new, severity))
    return {"violations": violations, "new": new, "baselined": len(violations) - len(new),
            "failed": failed, "updated_baseline": False}

def check_dependencies(store, config, files=None) -> list:
    """Flag imports that resolve to no known package (possible slopsquatting).
    Defaults to git-changed files; fully offline."""
    _log_op(store, "check_dependencies", "")
    if files is None:
        files = gitinfo.changed_source_files(store.paths.root)
    return _deps.unknown_imports(store.paths.root, files)

def _verify_check(name, ok, status, reasons, *, cap: int = 0) -> dict:
    """`count` is the true number of reasons; `reasons` is capped so a gate that
    JSON-dumps this verdict into an agent's context stays cheap. A caller sees
    it was capped from `count > len(reasons)`."""
    kept, _ = cap_items(reasons, cap)
    return {"name": name, "ok": ok, "status": status, "reasons": kept, "count": len(reasons)}

def _verify_tests(store) -> dict:
    """Run a recorded `test` (or `verify`) command if one exists; skip — never
    fail — when none is recorded, so the default gate stays instant static analysis."""
    names = {c["name"] for c in list_commands(store)}
    target = "test" if "test" in names else ("verify" if "verify" in names else None)
    if target is None:
        return _verify_check("tests", True, "skip", ["no 'test' command recorded (torsor commands --record)"])
    proc = run_command(store, target)
    code = getattr(proc, "returncode", None)
    ok = code == 0
    return _verify_check("tests", ok, "pass" if ok else "fail",
                         [] if ok else [f"`{target}` command exited {code}"])

def verify(store, config, files=None, *, severity=None, run_tests=False) -> dict:
    """The single deterministic verification gate: guard (new drift) + deps
    (slopsquatting) + staleness, and optionally a recorded test command. Composes
    the existing cores — no new checking logic — into one machine-checkable verdict
    designed as a loop-engineering / Stop-hook / CI completion condition.

    `files` defaults to git-changed so guard/deps judge the same change set (fast,
    offline). `ok` is the single boolean a gate reads; per-check `reasons` give the
    agent a fix list without re-running each tool."""
    _log_op(store, "verify", "")
    if files is None:
        files = gitinfo.changed_source_files(store.paths.root)

    guard_result = guard_run(store, config, files, strict=True, severity=severity)
    guard_reasons = [f"{v.file}:{v.line} — [{v.severity}] {v.message} (per {v.source})" for v in guard_result["new"]]
    dep_findings = check_dependencies(store, config, files)
    dep_reasons = [f"{f['file']}:{f['line']} — unknown import '{f['name']}'" for f in dep_findings]
    # Deliberately NOT scoped by `files`, unlike guard and deps. A staleness
    # finding's source is a NOTE path; `files` holds SOURCE files (git-changed
    # discovery filters to source extensions, so a .md never appears). The two
    # namespaces do not intersect, so filtering one by the other always yields
    # nothing. If pre-existing staleness should stop blocking an unrelated
    # change, the mechanism is a ratchet like the guard's baseline, not a name
    # filter.
    stale_findings = check_staleness(store, config)["findings"]
    stale_reasons = [f"[{r.kind}] {r.message}" for r in stale_findings]

    cap = config.budgets.max_items
    checks = [
        _verify_check("guard", not guard_result["failed"], "pass" if not guard_result["failed"] else "fail",
                      guard_reasons, cap=cap),
        _verify_check("deps", not dep_findings, "pass" if not dep_findings else "fail",
                      dep_reasons, cap=cap),
        _verify_check("staleness", not stale_findings, "pass" if not stale_findings else "fail",
                      stale_reasons, cap=cap),
    ]
    if run_tests:
        checks.append(_verify_tests(store))

    ok = all(c["ok"] for c in checks)
    summary = " ".join(f"{c['name']}:{c['status'] if c['status'] != 'fail' else str(c['count'])}" for c in checks)
    return {"ok": ok, "exit_code": 0 if ok else 1, "checks": checks, "summary": summary}

def pre_push(store, config) -> dict:
    """Pre-push hook core: advisory guard. Installed only when guard_on_push is
    on; the adapter maps `failed` to the process exit code so a failing guard can
    block the push. A no-op verdict when disabled."""
    if not config.automation.guard_on_push:
        return {"failed": False, "new": [], "skipped": True}
    result = guard_run(store, config, strict=True)
    return {"failed": result["failed"], "new": result["new"], "skipped": False}

def _proposed_text(path, tool_name: str, tool_input: dict) -> str | None:
    """The file content an Edit/Write *would* produce — reconstructed, never
    applied. None when it can't be known (missing file for an Edit, an
    old_string that doesn't match — Claude Code will reject that edit anyway)."""
    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        return None
    try:
        current = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    if old not in current:
        return None
    return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)

def pre_edit(store, config, tool_name, tool_input) -> dict | None:
    """PreToolUse edit-gate core: run the ADR rules against the *proposed*
    content of an Edit/Write, ratchet against the committed baseline, and hand
    back a verdict — None when there is nothing new to say (the common case,
    so the hook stays silent). Read-only: the gate never touches the file.
    `decision` is "advise" unless automation.guard_on_edit is "block" AND a new
    violation is severity=error; the guard never blocks by default (ADR 0012)."""
    mode = config.automation.guard_on_edit
    if mode == "off" or tool_name not in ("Edit", "Write") or not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not file_path:
        return None
    root = store.paths.root.resolve()
    path = Path(file_path)
    if not path.is_absolute():
        path = root / path
    try:
        relpath = path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None  # outside the project — not ours to judge
    if relpath.startswith(".torsor/"):
        return None  # memory writes are never architecture drift

    text = _proposed_text(path, tool_name, tool_input)
    if text is None:
        return None
    violations = [
        v
        for rule in guard.load_rules(store)
        if guard.scope_matches(relpath, rule.scope)
        for v in guard.violations_for_file(relpath, text, rule)
    ]
    new = _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))
    if not new:
        return None

    deny = mode == "block" and bool(guard.strict_failures(new, "error"))
    decision = "deny" if deny else "advise"
    lines = [f"- {v.file}:{v.line} [{v.severity}] {v.message} (per {v.source})" for v in new]
    head = (
        f"torsor guard: this {tool_name.lower()} would introduce {len(new)} new architecture "
        f"violation(s) against the project's ADRs:"
    )
    tail = (
        "Blocked (automation.guard_on_edit = block). Change the approach, or record a superseding ADR first."
        if deny else
        "Advisory: reconsider before proceeding, or record a superseding ADR if the rule is wrong."
    )
    return {"decision": decision, "new": new, "context": "\n".join([head, *lines, tail])}
