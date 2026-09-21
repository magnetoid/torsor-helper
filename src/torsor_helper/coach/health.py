from __future__ import annotations

from torsor_helper import cartographer, templates
from torsor_helper.guard import load_rules
from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_THIN_TARGETS = [
    ("charter", "Charter", templates.CHARTER),
    ("system_patterns", "System patterns", templates.SYSTEM_PATTERNS),
    ("tech_context", "Tech context", templates.TECH_CONTEXT),
]


def check_thin(store: Store) -> list[Recommendation]:
    out: list[Recommendation] = []
    for attr, label, seed in _THIN_TARGETS:
        path = getattr(store.paths, attr)
        if path.exists() and templates.is_unfilled(store.paths, path):
            out.append(Recommendation(
                kind="thin", severity="important",
                message=f"{label} is still the seed template — fill it in so the agent has real context.",
                action=f"Edit {path}", source=str(path), key=f"thin:{attr}",
            ))
    return out


def check_stale(store: Store) -> list[Recommendation]:
    path = store.paths.active_context
    if path.exists() and templates.is_unfilled(store.paths, path):
        return [Recommendation(
            kind="stale", severity="suggest",
            message="Active context is still the seed template — capture current focus with update_active / handoff.",
            action="run handoff or update_active", source=str(path), key="stale:active",
        )]
    return []


def check_unruled(store: Store) -> list[Recommendation]:
    decisions = sorted(store.paths.decisions_dir.glob("*.md")) if store.paths.decisions_dir.exists() else []
    rules = load_rules(store)
    if len(decisions) >= 2 and not rules:
        return [Recommendation(
            kind="unruled", severity="suggest",
            message=f"{len(decisions)} decisions recorded but no machine-readable rules — formalize the load-bearing ones so the guard can enforce them.",
            action="add a rules: block to an ADR's frontmatter", source=str(store.paths.decisions_dir), key="unruled",
        )]
    return []


def check_uncharted(store: Store, modules_in_map: set[str], *, map_current: bool | None = None,
                    mapped_at_ns: int | None = None) -> list[Recommendation]:
    """Source the map has not seen.

    "Source files minus modules that have symbols" was the whole check, and it
    confused NOT SCANNED with SCANNED, DEFINES NOTHING. On a real 3 200-file
    project that was 265 files right after a full `torsor map` — empty and
    re-export __init__.py, __main__.py, a main.tsx entry point, a vite.config.ts
    that only does `export default` — so it said "run `torsor map`" forever and
    running it changed nothing: the kind of false alarm that teaches people to
    stop reading the Coach (ADR 0010).

    So when the map can speak for itself, ask it: the fingerprint says whether
    anything changed since the last full map, and `mapped_at_ns` says what
    changed since the last map of any kind. Set difference is only the answer
    when there has never been a map at all."""
    if map_current:
        return []
    root = store.paths.root
    if mapped_at_ns is not None:
        changed = sorted(
            p.relative_to(root).as_posix() for p in cartographer.iter_source_files(root)
            if _mtime_ns(p) > mapped_at_ns
        )
        if not changed:
            return []
        return [Recommendation(
            kind="uncharted", severity="suggest",
            message=(f"The map is out of date — {len(changed)} source file(s) changed since the last "
                     f"`torsor map` (e.g. {changed[0]})."),
            action="torsor map", source=changed[0], key="uncharted",
        )]
    source = {p.relative_to(root).as_posix() for p in cartographer.iter_source_files(root)}
    missing = sorted(source - modules_in_map)
    if not missing:
        return []
    return [Recommendation(
        kind="uncharted", severity="suggest",
        message=f"{len(missing)} source module(s) not in the map (e.g. {missing[0]}) — run `torsor map`.",
        action="torsor map", source=missing[0], key="uncharted",
    )]


def _mtime_ns(path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


_UNCHARTED_LANGUAGE_MIN_FILES = 5


def check_uncharted_language(store: Store) -> list[Recommendation]:
    """A language with real presence in the repo but no available extractor —
    the map is silently blind to it. Index-free and deterministic."""
    from torsor_helper import languages

    counts: dict[str, int] = {}
    for path in cartographer.iter_files(store.paths.root, skip_hidden=True):
        for spec in languages.LANGUAGES.values():
            if path.suffix in spec.extensions:
                if not languages.is_available(spec.name):
                    counts[spec.name] = counts.get(spec.name, 0) + 1
                break
    out: list[Recommendation] = []
    for name, n in sorted(counts.items()):
        if n >= _UNCHARTED_LANGUAGE_MIN_FILES:
            out.append(Recommendation(
                kind="uncharted_language", severity="info",
                message=f"{n} {name} file(s) are invisible to the map — the [languages] extra isn't installed.",
                action="uv tool install 'torsor-helper[languages]'", source=name, key=f"uncharted_language:{name}",
            ))
    return out


def run_health(store: Store, modules_in_map: set[str], *, map_current: bool | None = None,
               mapped_at_ns: int | None = None) -> list[Recommendation]:
    return [
        *check_thin(store),
        *check_stale(store),
        *check_unruled(store),
        *check_uncharted(store, modules_in_map, map_current=map_current, mapped_at_ns=mapped_at_ns),
        *check_uncharted_language(store),
    ]
