from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

import yaml

from torsor_mem.models import Frontmatter, Note, Tier
from torsor_mem.paths import TorsorPaths

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_FM_BLOCK = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


class Store:
    def __init__(
        self,
        paths: TorsorPaths,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.paths = paths
        self.clock = clock

    # ---- static parsing helpers ----
    @staticmethod
    def parse_frontmatter(text: str) -> tuple[Frontmatter, str]:
        match = _FM_BLOCK.match(text)
        if not match:
            return Frontmatter(type="note"), text
        meta = yaml.safe_load(match.group(1)) or {}
        if "type" not in meta:
            meta["type"] = "note"
        return Frontmatter.model_validate(meta), match.group(2)

    @staticmethod
    def serialize(frontmatter: Frontmatter, title: str, body: str) -> str:
        meta = frontmatter.model_dump(exclude_none=True)
        yaml_block = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
        return f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"

    @staticmethod
    def extract_wikilinks(text: str) -> list[str]:
        out: list[str] = []
        for m in _WIKILINK.finditer(text):
            link = m.group(1).strip()
            if link and link not in out:
                out.append(link)
        return out

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def tier_for_path(paths: TorsorPaths, path: Path) -> Tier:
        p = Path(path).resolve()
        if p == paths.charter.resolve():
            return Tier.CHARTER
        if _within(p, paths.architecture_dir):
            return Tier.ARCHITECTURE
        if _within(p, paths.map_dir):
            return Tier.MAP
        if _within(p, paths.active_dir):
            return Tier.ACTIVE
        return Tier.EPISODIC


def _within(path: Path, parent: Path) -> bool:
    parent = parent.resolve()
    return path == parent or parent in path.parents
