"""The orchestration core: what the CLI and the MCP server are thin wrappers over.

This module is a façade. Each concern lives in its own submodule, and everything
public is re-exported here so `from torsor_helper import operations as ops` keeps
meaning what it always did for both adapters and the test suite.

    _shared / _state   index + embedder plumbing, non-derivable state paths
    memory             session digest, recall, remember, handoff, intent
    graph              map_repo and the symbol-graph queries on top of it
    commands           the learned command book
    decisions          authoring ADRs
    prompt_blocks      rules digest, primer, and their block writers
    gate               guard/deps/staleness, verify, and the push and edit gates
    maintenance        Coach, staleness marking, clean
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
    record_command,
    run_command,
)
from torsor_helper.operations.decisions import (  # noqa: F401  (facade re-exports)
    _find_adr,
    _next_adr_number,
    _slug,
    record_decision,
)
from torsor_helper.operations.graph import (  # noqa: F401  (facade re-exports)
    connect,
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
    check_staleness,
    clean,
    dismiss_recommendation,
    recommend,
)
from torsor_helper.operations.prompt_blocks import (  # noqa: F401  (facade re-exports)
    _scope_to_paths_glob,
    _write_managed_block,
    agent_rules,
    project_primer,
    write_primer_block,
    write_rules_block,
    write_scoped_rules,
)
from torsor_helper.operations.capture import (  # noqa: F401  (facade re-exports)
    _load_capture_state,
    _save_capture_state,
    auto_handoff,
    on_commit,
)
from torsor_helper.operations.gate import (  # noqa: F401  (facade re-exports)
    check_dependencies,
    dependency_targets,
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
    _open_index,
)

# The git wrapper lives in gitinfo (a leaf module). This alias keeps the private
# name the capture tests use.
_git_head = gitinfo.head

__all__ = [
    "agent_rules",
    "auto_handoff",
    "bootstrap_session",
    "check_dependencies",
    "dependency_targets",
    "check_drift",
    "check_staleness",
    "clean",
    "connect",
    "dismiss_recommendation",
    "get_intent",
    "guard_run",
    "hooks_status",
    "impact",
    "install_hooks",
    "list_commands",
    "map_repo",
    "new_drift",
    "on_commit",
    "pre_edit",
    "pre_push",
    "project_primer",
    "recall",
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
    "write_primer_block",
    "write_rules_block",
    "write_scoped_rules",
]
