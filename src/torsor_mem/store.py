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

    # ---- filesystem operations ----
    def scaffold(self, force: bool = False) -> None:
        from torsor_mem.templates import seed_files

        for directory in (
            self.paths.architecture_dir,
            self.paths.decisions_dir,
            self.paths.map_dir,
            self.paths.active_dir,
            self.paths.journal_dir,
            self.paths.index_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        for path, content in seed_files(self.paths).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if force or not path.exists():
                path.write_text(content, encoding="utf-8")

        gitignore = self.paths.base / ".gitignore"
        if force or not gitignore.exists():
            gitignore.write_text(".index/\n", encoding="utf-8")

    def write_note(
        self, path: Path, frontmatter: Frontmatter, title: str, body: str
    ) -> Note:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = frontmatter.model_copy()  # don't mutate the caller's object
        stamp = self.clock().isoformat(timespec="seconds")
        if frontmatter.created is None:
            frontmatter.created = stamp
        frontmatter.updated = stamp
        text = self.serialize(frontmatter, title, body)
        path.write_text(text, encoding="utf-8")
        return self.read_note(path)

    def read_note(self, path: Path) -> Note:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        frontmatter, raw_body = self.parse_frontmatter(text)
        title, body = _split_title(raw_body, fallback=path.stem)
        return Note(
            path=path,
            tier=self.tier_for_path(self.paths, path),
            frontmatter=frontmatter,
            title=title,
            body=body,
            content_hash=self.content_hash(text),
        )

    def iter_notes(self) -> Iterator[Note]:
        if not self.paths.base.exists():
            return
        index = self.paths.index_dir.resolve()
        for md in sorted(self.paths.base.rglob("*.md")):
            if index in md.resolve().parents:
                continue
            yield self.read_note(md)

    def append_journal(self, content: str, kind: str, links: list[str]) -> Path:
        now = self.clock()
        path = self.paths.journal_file(now.strftime("%Y-%m-%d"))
        path.parent.mkdir(parents=True, exist_ok=True)
        link_text = " ".join(f"[[{link}]]" for link in links)
        entry = (
            f"\n## {now.strftime('%H:%M')} · {kind}\n\n"
            f"{content.strip()}\n"
        )
        if link_text:
            entry += f"\nLinks: {link_text}\n"
        if not path.exists():
            header = self.serialize(
                Frontmatter(type="journal", tags=["journal"]),
                f"Journal {now.strftime('%Y-%m-%d')}",
                "",
            )
            path.write_text(header, encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        return path


def _within(path: Path, parent: Path) -> bool:
    parent = parent.resolve()
    return path == parent or parent in path.parents


def _split_title(body: str, fallback: str) -> tuple[str, str]:
    """Return (title, body-without-leading-H1)."""
    match = _H1.search(body)
    if match and body[: match.start()].strip() == "":
        title = match.group(1).strip()
        rest = body[match.end():].lstrip("\n")
        return title, rest
    return fallback, body
