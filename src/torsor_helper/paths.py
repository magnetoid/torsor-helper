from __future__ import annotations

from pathlib import Path


def contained(root, candidate) -> Path | None:
    """`candidate` resolved against `root`, or None when it lands outside it.

    The single containment check for every caller-supplied path. Two of those
    callers are MCP tools (`check_drift`, `verify`), so the path can come from a
    prompt-injected agent; without this, a `forbid_pattern` rule turns into a
    read oracle for any file on the machine, and `guard --update-baseline` then
    writes what it found into a committed file.

    Resolves before comparing, so `../`, an absolute path and a symlink pointing
    out of the tree are all rejected."""
    try:
        root = Path(root).resolve()
        path = Path(candidate)
        path = path if path.is_absolute() else root / path
        path = path.resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path


class TorsorPaths:
    """Resolves the .torsor/ directory layout relative to a project root."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @property
    def base(self) -> Path:
        return self.root / ".torsor"

    @property
    def config_file(self) -> Path:
        return self.base / "torsor.toml"

    @property
    def charter(self) -> Path:
        return self.base / "charter.md"

    @property
    def architecture_dir(self) -> Path:
        return self.base / "architecture"

    @property
    def system_patterns(self) -> Path:
        return self.architecture_dir / "system-patterns.md"

    @property
    def tech_context(self) -> Path:
        return self.architecture_dir / "tech-context.md"

    @property
    def decisions_dir(self) -> Path:
        return self.architecture_dir / "decisions"

    @property
    def map_dir(self) -> Path:
        return self.base / "map"

    @property
    def map_overview(self) -> Path:
        return self.map_dir / "overview.md"

    @property
    def active_dir(self) -> Path:
        return self.base / "active"

    @property
    def active_context(self) -> Path:
        return self.active_dir / "context.md"

    @property
    def progress(self) -> Path:
        return self.active_dir / "progress.md"

    @property
    def memory_dir(self) -> Path:
        return self.base / "memory"

    @property
    def journal_dir(self) -> Path:
        return self.memory_dir / "journal"

    @property
    def insights_dir(self) -> Path:
        return self.memory_dir / "insights"

    @property
    def llms_txt(self) -> Path:
        return self.base / "llms.txt"

    @property
    def commands_file(self) -> Path:
        # The learned command book — committed Markdown so it travels with the repo.
        return self.base / "commands.md"

    @property
    def baseline_file(self) -> Path:
        # Committed, reviewable drift baseline — a sibling of the charter, NOT
        # under the disposable .index/ (a baseline is source-of-truth config).
        return self.base / "baseline.json"

    @property
    def index_dir(self) -> Path:
        return self.base / ".index"

    @property
    def map_dependencies(self) -> Path:
        # The module diagram gets its own note. It used to be appended into
        # map/overview.md, which map_repo re-renders from scratch — so the
        # diagram vanished on the next commit, since the post-commit hook
        # remaps every time.
        return self.map_dir / "dependencies.md"

    @property
    def gitattributes(self) -> Path:
        # Committed, unlike .torsor/.gitignore's subjects: it is how a clone
        # learns that journals union-merge and map notes are regenerated.
        return self.base / ".gitattributes"

    @property
    def state_dir(self) -> Path:
        # Small, machine-local state that does NOT rebuild from Markdown: the
        # user's Coach dismissals and the auto-handoff watermark. It lived in
        # .index/ until `clean --deep` (which rmtree's that directory, correctly,
        # because everything else in it IS derivable) started silently
        # un-dismissing every recommendation. Git-ignored — the watermark is a
        # local git HEAD and means nothing on another machine.
        return self.base / "state"

    @property
    def index_db(self) -> Path:
        return self.index_dir / "torsor.db"

    @property
    def claude_settings(self) -> Path:
        # Claude Code project settings — NOT under .torsor/. Auto-capture hook
        # entries are merged into its "hooks" section (foreign keys preserved).
        return self.root / ".claude" / "settings.json"

    @property
    def claude_rules_dir(self) -> Path:
        # Path-scoped Claude Code rules (`paths:` frontmatter → loaded only when a
        # matching file is touched). torsor owns exactly this subdirectory and
        # nothing beside it, so a user's own .claude/rules/*.md are never touched.
        return self.root / ".claude" / "rules" / "torsor"

    @property
    def claude_settings_local(self) -> Path:
        # Git-ignored local variant, for hook entries a user doesn't want committed.
        return self.root / ".claude" / "settings.local.json"

    def journal_file(self, date_str: str, author: str = "") -> Path:
        """`<date>.md`, or `<date>.<author>.md` when journals are partitioned.

        The date stays the *leading* token either way: `clean` reads the
        retention date straight out of the stem, and a suffix in front of it
        would have silently switched journal expiry off."""
        stem = f"{date_str}.{author}" if author else date_str
        return self.journal_dir / f"{stem}.md"
