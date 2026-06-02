from __future__ import annotations

from pathlib import Path


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
    def baseline_file(self) -> Path:
        # Committed, reviewable drift baseline — a sibling of the charter, NOT
        # under the disposable .index/ (a baseline is source-of-truth config).
        return self.base / "baseline.json"

    @property
    def index_dir(self) -> Path:
        return self.base / ".index"

    @property
    def index_db(self) -> Path:
        return self.index_dir / "torsor.db"

    def journal_file(self, date_str: str) -> Path:
        return self.journal_dir / f"{date_str}.md"
