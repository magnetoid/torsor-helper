"""The orchestration core: what the CLI and the MCP server are thin wrappers over.

This module is a façade. Each concern lives in its own submodule, and everything
public is re-exported here so `from torsor_helper import operations as ops` keeps
meaning what it always did for both adapters and the test suite.

    _shared / _state   index + embedder plumbing, non-derivable state paths
    memory             session digest, recall, remember, handoff, intent
    graph              map_repo and the symbol-graph queries on top of it
    commands           the learned command book and the op-frequency log
    decisions          authoring ADRs, adopting practice packs
    prompt_blocks      rules digest, primer, model policy, and their block writers
    gate               guard/deps/staleness, verify, and the push and edit gates
    maintenance        Coach, staleness marking, clean, consolidate
    capture            auto-handoff and the post-commit capture
    hooks_ops          installing and reporting the hooks (CLI-only, ADR 0009)

Submodules import each other by full path and never this façade — it is
half-initialised while it loads (ADR 0014). One consequence worth knowing:
monkeypatching a name *here* no longer intercepts a call one submodule makes to
another. Patch the submodule that owns the name instead.
"""
from __future__ import annotations


from torsor_helper import gitinfo

from torsor_helper.operations.commands import (  # noqa: F401  (facade re-exports)
    _CMD_RE,
    list_commands,
    recipes,
    record_command,
    run_command,
)
from torsor_helper.operations.decisions import (  # noqa: F401  (facade re-exports)
    _find_adr,
    _next_adr_number,
    _slug,
    adopt_practices,
    list_practices,
    record_decision,
)
from torsor_helper.operations.graph import (  # noqa: F401  (facade re-exports)
    connect,
    export_project,
    find_targets,
    impact,
    map_repo,
)
from torsor_helper.operations.memory import (  # noqa: F401  (facade re-exports)
    _BOOTSTRAP_ALLOC,
    _COACH_FRACTION,
    _RECENT_JOURNAL_FRACTION,
    bootstrap_session,
    get_intent,
    recall,
    record_handoff,
    remember,
    session_start_context,
    update_active,
)
from torsor_helper.operations._state import _coach_state_path, _state_file  # noqa: F401
from torsor_helper.operations.maintenance import (  # noqa: F401  (facade re-exports)
    _set_note_status,
    stats,
    _snapshot_complexity,
    check_staleness,
    clean,
    consolidate,
    dismiss_recommendation,
    recommend,
)
from torsor_helper.operations.prompt_blocks import (  # noqa: F401  (facade re-exports)
    _scope_to_paths_glob,
    _write_managed_block,
    agent_rules,
    model_policy,
    model_policy_json,
    project_primer,
    write_model_policy,
    write_primer_block,
    write_rules_block,
    write_scoped_rules,
)
from torsor_helper.operations.capture import (  # noqa: F401  (facade re-exports)
    _load_capture_state,
    _op_totals,
    _save_capture_state,
    auto_handoff,
    on_commit,
)
from torsor_helper.operations.gate import (  # noqa: F401  (facade re-exports)
    check_dependencies,
    check_drift,
    guard_run,
    new_drift,
    pre_edit,
    pre_push,
    verify,
)
from torsor_helper.operations.hooks_ops import (  # noqa: F401  (facade re-exports)
    hooks_status,
    install_hooks,
    uninstall_hooks,
)
from torsor_helper.operations._shared import (  # noqa: F401  (facade re-exports)
    _EMBEDDER_CACHE,
    _embedder_for,
    _log_op,
    _open_index,
)

# The git wrapper lives in gitinfo (a leaf module). These aliases keep the
# private names the capture tests and older call sites use.
_source_exts = gitinfo.source_extensions
_rel_to_root = gitinfo.rel_to_root
_git_changed = gitinfo.changed_source_files
_git_changed_in_commit = gitinfo.commit_source_files
_git_out = gitinfo.output
_git_head = gitinfo.head


# ---- Command book: learn & replay the project's commands ----

# ---- Op frequency log: learn which deterministic lookups recur ----

# ---- Auto-capture hooks: memory that captures itself on the git / agent
# lifecycle. torsor is never the scheduler (no daemon) — git and Claude Code
# invoke `torsor hooks run <event>`, which dispatches into the cores below.
# Every core is deterministic, offline, and flag-guarded (config.automation).

__all__ = [
    "adopt_practices",
    "agent_rules",
    "annotations",
    "auto_handoff",
    "bootstrap_session",
    "check_dependencies",
    "check_drift",
    "check_staleness",
    "clean",
    "connect",
    "consolidate",
    "dismiss_recommendation",
    "export_project",
    "find_targets",
    "get_intent",
    "gitinfo",
    "guard_run",
    "hooks_status",
    "impact",
    "install_hooks",
    "list_commands",
    "list_practices",
    "map_repo",
    "model_policy",
    "model_policy_json",
    "new_drift",
    "on_commit",
    "pre_edit",
    "pre_push",
    "project_primer",
    "recall",
    "recipes",
    "recommend",
    "record_command",
    "record_decision",
    "record_handoff",
    "remember",
    "run_command",
    "session_start_context",
    "uninstall_hooks",
    "update_active",
    "verify",
    "write_model_policy",
    "write_primer_block",
    "write_rules_block",
    "write_scoped_rules",
]
