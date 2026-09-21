from __future__ import annotations

import hashlib
import os
import re
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterator

import yaml

try:  # libyaml, when PyYAML was built against it — same grammar, C speed
    from yaml import CSafeLoader as _YamlLoader
except ImportError:  # pragma: no cover - pure-Python PyYAML
    from yaml import SafeLoader as _YamlLoader
from pydantic import ValidationError

from torsor_helper.models import Frontmatter, Note, Tier
from torsor_helper.paths import TorsorPaths

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# A bare name or a dotted path, both plausible spellings of a symbol. No
# leading dash, so `--json` and `-r` never look like code identifiers.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_MAX_MENTIONS = 200
_FM_BLOCK = re.compile(r"^---[ \t]*\n(.*?)^---[ \t]*\n?(.*)$", re.DOTALL | re.MULTILINE)
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


# Derived directories under .torsor/ that never belong in git: the index
# rebuilds from Markdown, and state/ holds machine-local dismissals plus a git
# watermark that means nothing on another machine.
_IGNORED = (".index/", "state/")


def ensure_ignored(paths) -> None:
    """Add any missing entry to .torsor/.gitignore, in place. Projects
    scaffolded before state/ existed would otherwise commit it."""
    gitignore = paths.base / ".gitignore"
    try:
        current = gitignore.read_text(encoding="utf-8").split() if gitignore.exists() else []
        missing = [line for line in _IGNORED if line not in current]
        if missing:
            body = "".join(f"{line}\n" for line in [*current, *missing])
            gitignore.parent.mkdir(parents=True, exist_ok=True)
            gitignore.write_text(body, encoding="utf-8")
    except OSError:
        pass  # advisory housekeeping; never break the caller over it


def state_file(paths, name: str):
    """Path to a non-derivable state file under .torsor/state/, migrating one
    written by an older version out of .index/ and making sure the directory is
    git-ignored. Migration on read keeps it to a single call site.

    These two files — the Coach's dismissals and the auto-handoff watermark —
    are the only things under .torsor/ that neither rebuild from Markdown nor
    belong in git, which is why they get their own directory: `clean --deep`
    removes .index/ wholesale, and that used to take them with it.
    """
    target = paths.state_dir / name
    legacy = paths.index_dir / name
    if not target.exists() and legacy.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            legacy.replace(target)
        except OSError:
            return legacy  # unwritable; better to keep reading the old one
    ensure_ignored(paths)
    return target


class Store:
    def __init__(
        self,
        paths: TorsorPaths,
        clock: Callable[[], datetime] = datetime.now,
        journal_partition: str = "date",
    ) -> None:
        self.paths = paths
        self.clock = clock
        # One layout knob, passed in like the clock rather than read from
        # torsor.toml in here, because Store has to stay usable on a project
        # whose config is malformed — that is the whole reason `remember` and
        # `handoff` load without it.
        self.journal_partition = journal_partition
        self._author: str | None = None

    # ---- static parsing helpers ----
    @staticmethod
    def parse_frontmatter(text: str) -> tuple[Frontmatter, str]:
        # Markdown is hand-editable by design, so frontmatter must be parsed
        # best-effort: a malformed note degrades to type="note", never raises
        # (one bad note must not take down indexing/recall for the project).
        match = _FM_BLOCK.match(text)
        if not match:
            return Frontmatter(type="note"), text
        try:
            meta = yaml.load(match.group(1), Loader=_YamlLoader) or {}
        except yaml.YAMLError:
            return Frontmatter(type="note"), text
        if not isinstance(meta, dict):
            return Frontmatter(type="note"), match.group(2)
        for key in ("created", "updated"):
            # YAML turns an unquoted `created: 2026-06-01` into a date object
            if isinstance(meta.get(key), (date, datetime)):
                meta[key] = meta[key].isoformat()
        if not isinstance(meta.get("type"), str):
            meta["type"] = "note"
        for key in ("tags", "links"):
            # `tags: architecture` is a natural thing to hand-write. Validation
            # used to reject it and the whole block was thrown away with it,
            # taking status, kind and rules along.
            if isinstance(meta.get(key), str):
                meta[key] = [meta[key]]
        try:
            return Frontmatter.model_validate(meta), match.group(2)
        except ValidationError:
            return Frontmatter(type="note"), match.group(2)

    @staticmethod
    def serialize(frontmatter: Frontmatter, title: str, body: str) -> str:
        meta = frontmatter.model_dump(exclude_none=True)
        yaml_block = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
        return f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"

    @staticmethod
    def extract_wikilinks(text: str) -> list[str]:
        """Link *targets*, in order, deduplicated.

        A target is the part before `|` (the display alias) and before `#` (a
        heading anchor) — both ordinary Markdown-wiki forms. Taking the raw
        inner text meant `[[charter|the charter]]` resolved to nothing, and the
        staleness checker then reported it as a dangling link: a false positive
        in the detector that exists precisely to have none (ADR 0010).

        A target containing "/" keeps it: `[[architecture/decisions/0001-x]]`
        means that path tail, not a basename."""
        out: list[str] = []
        for m in _WIKILINK.finditer(text):
            target = m.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            if target and target not in out:
                out.append(target)
        return out

    @staticmethod
    def extract_symbol_mentions(text: str) -> list[str]:
        """Code identifiers a note names in `backticks`, in order, deduplicated.

        This is the note→symbol half of the graph: `[[wikilinks]]` link notes to
        notes, and this links a note to the code it is *about*, which is what
        makes "which decisions mention this symbol" answerable.

        Deliberately dumb and deliberately unfiltered against the symbols table.
        A token is kept when it reads like an identifier, and whether it names a
        real symbol is decided at query time by joining — because filtering here
        would tie the feature to the order the note index and the symbol map
        happen to be built in, and reindex screens on (mtime, size), so a note
        written before the first `torsor map` would never be looked at again.

        Fenced blocks are stripped first: a code sample is an illustration, not
        a claim about a symbol. A dotted `ops.recall` yields both itself and
        `recall`, since either spelling may be what the symbol table holds."""
        text = _FENCE.sub("\n", text)
        out: list[str] = []
        for m in _INLINE_CODE.finditer(text):
            token = m.group(1).strip().removesuffix("()")
            if not _IDENTIFIER.fullmatch(token):
                continue
            for candidate in (token, token.rsplit(".", 1)[-1]):
                if candidate not in out:
                    out.append(candidate)
            # One note must not be able to flood the table. A note naming 200
            # distinct symbols is a generated index, not a decision about code.
            if len(out) >= _MAX_MENTIONS:
                break
        return out[:_MAX_MENTIONS]

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def tier_for_path(paths: TorsorPaths, path: Path) -> Tier:
        """Which stability tier a note file belongs to, by position.

        The anchors are resolved once per TorsorPaths and cached: this runs once
        per note inside read_note, and reindex reads every note, so resolving
        four anchors per call meant thousands of syscalls per map — 24s of a
        61s cold map over 2k notes."""
        raw, resolved = _tier_anchors(paths)
        # The common caller passes a path built from these same anchors, so the
        # unresolved comparison matches without touching the filesystem. Only a
        # path from somewhere else falls through to resolve() — which is what
        # keeps a symlinked note classified by where it really lives.
        tier = _match_tier(Path(path), raw)
        if tier is None:
            tier = _match_tier(Path(path).resolve(), resolved)
        return tier if tier is not None else Tier.EPISODIC

    # ---- filesystem operations ----
    def scaffold(self, force: bool = False) -> None:
        from torsor_helper.templates import seed_files

        for directory in (
            self.paths.architecture_dir,
            self.paths.decisions_dir,
            self.paths.map_dir,
            self.paths.active_dir,
            self.paths.journal_dir,
            self.paths.insights_dir,
            self.paths.index_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        for path, content in seed_files(self.paths).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if force or not path.exists():
                path.write_text(content, encoding="utf-8")

        gitignore = self.paths.base / ".gitignore"
        if force or not gitignore.exists():
            gitignore.write_text("".join(f"{line}\n" for line in _IGNORED), encoding="utf-8")

        # Committed, unlike everything .gitignore covers: it is how a clone
        # learns that journals union-merge. The custom map driver it names still
        # needs a per-clone `torsor merge install` — see merge.py.
        from torsor_helper.merge import write_attributes

        write_attributes(self.paths)

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
        # utf-8-sig: a Windows editor writes a BOM, which would otherwise sit
        # in front of the "---" and hide the whole frontmatter block. Every
        # other reader in the codebase (cartographer, guard, deps) already does
        # this; read_note did not, so a BOM'd note silently lost its tier.
        text = path.read_text(encoding="utf-8-sig")
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

    def iter_note_paths(self) -> Iterator[Path]:
        """All note files in the pyramid (excluding the derived directories), in
        sorted order — without reading them (cheap stat-level iteration).

        Prunes DURING traversal, the way cartographer.iter_files does. The
        previous `rglob("*.md")` + `index in md.resolve().parents` filter called
        resolve() — a syscall — once per note, and reindex walks this on every
        recall: measured at 5.8s of an 11.8s recall over 5k notes, which is most
        of what made recall feel slow."""
        base = self.paths.base
        if not base.exists():
            return
        skip = {self.paths.index_dir.name, self.paths.state_dir.name}
        for dirpath, dirnames, filenames in os.walk(base):
            if Path(dirpath) == base:
                dirnames[:] = [d for d in dirnames if d not in skip]
            dirnames.sort()
            here = Path(dirpath)
            for name in sorted(filenames):
                if name.endswith(".md"):
                    yield here / name

    def iter_notes(self) -> Iterator[Note]:
        for md in self.iter_note_paths():
            try:
                note = self.read_note(md)
            except (OSError, UnicodeDecodeError) as exc:
                warnings.warn(f"skipping unreadable note {md}: {exc}")
                continue
            yield note

    def journal_author(self) -> str:
        """The author slug this Store partitions journals by, cached per Store
        because it shells out to git. Empty unless partitioning is on."""
        if self.journal_partition != "date-author":
            return ""
        if self._author is None:
            from torsor_helper import gitinfo

            self._author = gitinfo.author_slug(self.paths.root)
        return self._author

    def append_journal(self, content: str, kind: str, links: list[str]) -> Path:
        now = self.clock()
        day = now.strftime("%Y-%m-%d")
        path = self.paths.journal_file(day, self.journal_author())
        path.parent.mkdir(parents=True, exist_ok=True)
        link_text = " ".join(f"[[{link}]]" for link in links)
        entry = (
            f"\n## {now.strftime('%H:%M')} · {kind}\n\n"
            f"{content.strip()}\n"
        )
        if link_text:
            entry += f"\nLinks: {link_text}\n"
        if not path.exists():
            # Stamped with the journal's own date, NOT the wall clock: two
            # branches that both start the day's journal must write a
            # byte-identical header, or the union merge that keeps both sides'
            # entries unions the frontmatter too and leaves a duplicate
            # created:/updated: pair inside the `---` block, one per merge.
            # The date is also the truer answer — the stamp was never refreshed
            # on append, so it only ever meant "this day".
            stamp = f"{day}T00:00:00"
            header = self.serialize(
                Frontmatter(type="journal", tags=["journal"], created=stamp, updated=stamp),
                f"Journal {day}",
                "",
            )
            path.write_text(header, encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        return path


_TIER_ANCHOR_CACHE: dict[Path, tuple[tuple[Path, ...], tuple[Path, ...]]] = {}


def _match_tier(p: Path, anchors: tuple[Path, ...]) -> Tier | None:
    if p == anchors[0]:
        return Tier.CHARTER
    for parent, tier in zip(anchors[1:], (Tier.ARCHITECTURE, Tier.MAP, Tier.ACTIVE)):
        if p == parent or parent in p.parents:
            return tier
    return None


def _tier_anchors(paths: TorsorPaths):
    """((charter, architecture, map, active) as written, and resolved).

    Computed once per project root. tier_for_path runs inside read_note, and
    reindex reads every note, so resolving four anchors per call cost thousands
    of syscalls per map. Keyed on the RESOLVED root because the CLI passes a
    relative Path("."). The layout does not move while a process runs."""
    key = paths.root.resolve()
    cached = _TIER_ANCHOR_CACHE.get(key)
    if cached is None:
        raw = (paths.charter, paths.architecture_dir, paths.map_dir, paths.active_dir)
        cached = (raw, tuple(a.resolve() for a in raw))
        _TIER_ANCHOR_CACHE[key] = cached
    return cached


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
