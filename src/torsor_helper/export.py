from __future__ import annotations

import re

from torsor_helper import db, templates
from torsor_helper.cartographer import norm_path
from torsor_helper.models import Frontmatter
from torsor_helper.store import Store

_MERMAID_HEADING = "## Module dependencies"


def _summary(body: str) -> str:
    """First non-empty, non-heading prose line (underscores stripped) — used as
    the llms.txt blockquote summary even when the charter is still seed text."""
    for line in body.splitlines():
        s = line.strip().strip("_").strip()
        if s and not s.startswith("#"):
            return s
    return ""


def _rel(path, paths) -> str:
    return path.relative_to(paths.base).as_posix()


def render_llms_txt(store: Store) -> str:
    """Serialize the pyramid to the llms.txt convention (https://llmstxt.org):
    H1 title, blockquote summary, then H2 sections with links to the key notes.
    A portable, human-diffable view of project intent for tools that don't speak
    torsor's MCP protocol."""
    paths = store.paths
    title, summary = "Project", ""
    # llms.txt is written for language models; an unfilled charter would give
    # them "Describe the product in 2-3 sentences." as the project summary.
    if paths.charter.exists() and not templates.is_unfilled(paths, paths.charter):
        charter = store.read_note(paths.charter)
        title = charter.title or "Project"
        summary = _summary(charter.body)

    lines = [f"# {title}", ""]
    if summary:
        lines += [f"> {summary}", ""]

    def section(name, items):
        items = [it for it in items if it]
        if not items:
            return
        lines.append(f"## {name}")
        lines.append("")
        for note_title, url in items:
            lines.append(f"- [{note_title}]({url})")
        lines.append("")

    def link(path):
        return (store.read_note(path).title, _rel(path, paths)) if path.exists() else None

    section("Charter", [link(paths.charter)])

    arch = [link(paths.system_patterns), link(paths.tech_context)]
    if paths.decisions_dir.exists():
        arch += [link(p) for p in sorted(paths.decisions_dir.glob("*.md"))]
    section("Architecture", arch)

    section("Active", [link(paths.active_context), link(paths.progress)])

    if paths.insights_dir.exists():
        section("Memory", [link(p) for p in sorted(paths.insights_dir.glob("*.md"))])

    return "\n".join(lines).strip() + "\n"


def _node_id(name: str) -> str:
    return "n_" + re.sub(r"[^0-9A-Za-z_]", "_", name)


def render_module_mermaid(conn) -> str:
    """A GitHub-renderable Mermaid `graph TD` of module->module dependency edges,
    collapsed from the resolved symbol edges. Only edges between known repo
    modules are drawn (external imports and self-edges dropped). Empty string
    when there are no such edges."""
    known = {norm_path(m) for m in db.modules(conn)}
    pairs = set()
    for module, resolved in db.module_edges(conn):
        # `module` is a file relpath (needs norm_path); `resolved` is already
        # the canonical resolved_module key — never re-normalize it.
        src, dst = norm_path(module), resolved
        if src in known and dst in known and src != dst:
            pairs.add((src, dst))
    if not pairs:
        return ""

    nodes = sorted({n for pair in pairs for n in pair})
    lines = ["```mermaid", "graph TD"]
    for n in nodes:
        lines.append(f'    {_node_id(n)}["{n}"]')
    for src, dst in sorted(pairs):
        lines.append(f"    {_node_id(src)} --> {_node_id(dst)}")
    lines.append("```")
    return "\n".join(lines)


def export_project(store: Store, config) -> dict:
    """Write .torsor/llms.txt and the Mermaid module diagram.

    The diagram is its own note (map/dependencies.md), not a section appended
    to the map overview: map_repo re-renders the overview from the symbol
    table, so a diagram living there was erased by the next `torsor map` — and
    the post-commit hook runs one on every commit. Idempotent: re-running
    replaces the note, never accumulates."""
    paths = store.paths
    paths.llms_txt.write_text(render_llms_txt(store), encoding="utf-8")

    diagram_written = False
    if paths.index_db.exists():
        conn = db.connect(paths.index_db)
        try:
            diagram = render_module_mermaid(conn)
        finally:
            conn.close()
        if diagram:
            store.write_note(
                paths.map_dependencies,
                Frontmatter(type="map", status="derived", tags=["map"]),
                "Module dependencies",
                f"{_MERMAID_HEADING}\n\n{diagram}\n",
            )
            diagram_written = True

    return {"llms_txt": str(paths.llms_txt), "diagram": diagram_written}
