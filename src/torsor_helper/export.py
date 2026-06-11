from __future__ import annotations

import re

from torsor_helper import db
from torsor_helper.cartographer import norm_module
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
    if paths.charter.exists():
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
    known = {norm_module(m) for m in db.modules(conn)}
    pairs = set()
    for module, resolved in db.module_edges(conn):
        src, dst = norm_module(module), norm_module(resolved)
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


def _strip_mermaid(body: str) -> str:
    return body.split("\n" + _MERMAID_HEADING, 1)[0].rstrip()


def export_project(store: Store, config) -> dict:
    """Write .torsor/llms.txt and inject a Mermaid module diagram into the
    repo-map overview note. Idempotent — re-running replaces, never accumulates."""
    paths = store.paths
    paths.llms_txt.write_text(render_llms_txt(store), encoding="utf-8")

    diagram_written = False
    if paths.index_db.exists() and paths.map_overview.exists():
        conn = db.connect(paths.index_db)
        try:
            diagram = render_module_mermaid(conn)
        finally:
            conn.close()
        if diagram:
            note = store.read_note(paths.map_overview)
            body = _strip_mermaid(note.body)
            new_body = f"{body}\n\n{_MERMAID_HEADING}\n\n{diagram}\n"
            store.write_note(paths.map_overview, note.frontmatter, note.title, new_body)
            diagram_written = True

    return {"llms_txt": str(paths.llms_txt), "diagram": diagram_written}
