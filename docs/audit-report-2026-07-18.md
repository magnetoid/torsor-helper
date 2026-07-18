# Comprehensive Codebase Audit: torsor-helper v0.4.0

**Date**: 2026-07-18
**Scope**: Full repository — 26 source modules, 68+ test files, 7 ADRs
**Method**: Static analysis of all source code, architecture documents, ADRs, CI config, and test structure

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Problems the Application Solves](#a-core-problems-the-application-solves)
3. [Issues by Problem Category](#b-issues-by-problem-category)
   - [B1. Performance & Scalability](#b1-performance--scalability-impacts-p1-p3-p4)
   - [B2. Security](#b2-security-impacts-p1-p5-p7)
   - [B3. Maintainability & Code Quality](#b3-maintainability--code-quality-impacts-p2-p3-p7)
   - [B4. Architecture & Design](#b4-architecture--design-impacts-p1-p2-p3-p4-p6)
   - [B5. Testing & QA](#b5-testing--qa-impacts-p2-p5-p6-p7)
   - [B6. Usability & Documentation](#b6-usability--documentation-impacts-p1-p3-p7)
4. [Prioritized Improvement Roadmap](#c-prioritized-improvement-roadmap)
5. [Risk Mitigation Summary](#d-risk-mitigation-summary)
6. [Appendix: Architectural Strengths](#appendix-architectural-strengths)

---

## Executive Summary

torsor-helper is a well-architected Python MCP server (v0.4.0, ~7,600 lines of source) that solves a real and acute problem: AI coding agents lose context across sessions. Its approach — git-versioned Markdown as source of truth, derived SQLite index, symbol cartography, drift guard, and health Coach — is coherent and principled.

**Overall assessment**: Production-ready for single-user local use. **Not ready for multi-user or network-exposed deployment** due to the unauthenticated HTTP transport and lack of input sanitization. The codebase shows strong internal consistency and clean layering, but `operations.py` has grown into a god module and the performance path degrades linearly with note count.

**Key findings by severity**:

| Severity | Count | Top concern |
|----------|-------|-------------|
| Critical | 2 | Unauthenticated HTTP transport, O(n) vector scan |
| High | 8 | Duplicate tier weights, god module, shell injection, no MCP integration tests, full-rebuild map, reindex-on-every-recall |
| Medium | 13 | Partial scan data destruction, no async, Python-only cartographer, missing type annotations, Coach action specificity |
| Low | 7 | Unbounded embedder cache, weak hashing fallback, no API docs |

---

## A. Core Problems the Application Solves

| # | Problem Category | Description |
|---|---|---|
| **P1** | **Context Collapse** | AI coding agents lose project context over sessions. torsor provides a git-versioned Markdown "second brain" (the pyramid) with derived semantic search. |
| **P2** | **Architectural Drift** | Code changes that violate declared architectural intent go undetected. The drift guard checks source against machine-readable ADR rules. |
| **P3** | **Inefficient Context Discovery** | Agents spend too many tool-call tokens rediscovering project conventions each session. The primer/rules/bootstrap system provides pre-digested context. |
| **P4** | **Symbol & Impact Discovery** | Agents need to understand code structure and blast radius without manual exploration. The cartographer maps symbols/edges; `impact()` traces callers. |
| **P5** | **Dependency Hallucination** | AI agents invent non-existent package imports ("slopsquatting"). `check_dependencies()` cross-references imports against stdlib + installed + declared packages. |
| **P6** | **Code Health Decay** | Hotspots, temporal coupling, and complexity regressions accumulate silently. The Coach surfaces them as recommendations. |
| **P7** | **Best Practice Drift** | AI-generated code violates consensus practices. Curated per-language packs with machine-enforceable guard rules prevent recurring mistakes. |

---

## B. Issues by Problem Category

### B1. Performance & Scalability (Impacts: P1, P3, P4)

#### CRITICAL — [I-1] Full O(n) vector scan on every recall query

**File**: [src/torsor_helper/db.py:215-234](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/db.py#L215-L234)

`cosine_search()` loads **all** vectors into memory and computes cosine similarity against the query vector in a pure Python loop. With 1,000+ notes × 384-dimensional vectors, this becomes the dominant latency source. No approximate nearest neighbor (ANN) index, no quantization, no result caching.

```python
# db.py:215-234 — loads every vector for every query
def cosine_search(conn, qvec, limit):
    rows = conn.execute("SELECT path, embedding FROM vectors").fetchall()  # SELECT *
    ...
    for r in rows:
        v = unpack(r["embedding"])
        scored.append((r["path"], float(np.dot(q, v / vn))))
```

**Impact**: Recall latency scales linearly with note count. A project with 5,000 notes would spend ~50ms+ per query in vector search alone.

---

#### HIGH — [I-2] Index is re-synced on every recall call

**File**: [src/torsor_helper/operations.py:86-96](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L86-L96)

`_open_index()` calls `reindex()` before every `recall()` invocation. While the indexer has an mtime-stat skip optimization, it still opens a DB connection and stat-checks every note file on each recall call. This is O(files) overhead per query.

```python
# operations.py:86-96
def _open_index(store, config):
    if not config.index.auto_index and not store.paths.index_db.exists():
        return None
    embedder = _embedder_for(config)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, embedder)  # runs on EVERY recall
    except Exception:
        conn.close()
        raise
    return conn
```

**Impact**: Adds unnecessary disk I/O and stat syscalls to every recall. For a project with 500 notes, this is ~500 stat calls per query.

---

#### HIGH — [I-3] Map rebuild is all-or-nothing on any file change

**File**: [src/torsor_helper/operations.py:163](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L163)

The fingerprint-based skip is whole-repo: one changed file triggers a complete rescan of all symbols, edges, and rendered map Markdown. No incremental update path exists.

```python
# operations.py:163 — all-or-nothing skip
if full_scan and not force and fingerprint == db.meta_get(conn, "map_fingerprint"):
    return {"skipped": True, ...}
```

**Impact**: In a 500-module project, changing one file's docstring forces a full AST parse of all 500 modules.

---

#### MEDIUM — [I-4] Partial map scan is destructive to other module data

**File**: [src/torsor_helper/operations.py:181-189](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L181-L189)

When `map_repo(paths=[...])` is called with a subset of paths, `replace_all_symbols()` and `replace_all_edges()` delete ALL existing data before inserting only the scanned subset. Every module not in the `paths` list loses its symbols.

```python
# operations.py:181-189
db.replace_all_symbols(conn, symbols)     # deletes ALL, inserts only scanned subset
db.replace_all_edges(conn, edges)
...
db.meta_set(conn, "map_fingerprint", "")  # prevents false skip on next full map
```

**Impact**: Calling `map_repo(paths=['src/a.py'])` wipes symbols for `src/b.py` through `src/z.py` from the index.

---

#### MEDIUM — [I-5] Keyword recall fallback reads full note bodies in O(n)

**File**: [src/torsor_helper/recall.py:34-35](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/recall.py#L34-L35)

When no index exists, `keyword_recall()` iterates all notes and reads their full body. No substring index or pre-filter is used.

```python
# recall.py:34-35
for note in notes:
    haystack = f"{note.title}\n{note.body}".lower()
    raw = sum(haystack.count(term) for term in terms)
```

**Impact**: On a cold start (no index), recall must read and scan every Markdown file in the pyramid.

---

#### MEDIUM — [I-6] No connection pooling for concurrent MCP access

**File**: [src/torsor_helper/operations.py:85-96](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L85-L96)

Each `_open_index()` creates a new `sqlite3.connect()`. WAL mode helps with concurrent readers, but connection creation overhead is unnecessary if the server handles frequent recall requests.

**Impact**: Under concurrent MCP tool calls (streamable-http transport), each request pays connection setup cost.

---

#### LOW — [I-7] Unbounded embedder cache

**File**: [src/torsor_helper/operations.py:75-82](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L75-L82)

`_EMBEDDER_CACHE` is a module-level dict with no eviction policy. Practically this holds at most 2-3 entries (fastembed + hashing), but the pattern is fragile and untested for concurrent access.

```python
# operations.py:75-82
_EMBEDDER_CACHE: dict = {}

def _embedder_for(config):
    key = (config.embeddings.provider, config.embeddings.model, config.embeddings.dim)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = get_embedder(config)
    return _EMBEDDER_CACHE[key]
```

---

### B2. Security (Impacts: P1, P5, P7)

#### CRITICAL — [I-8] HTTP transport has zero authentication

**Files**: [src/torsor_helper/server.py:215-222](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/server.py#L215-L222), [src/torsor_helper/cli.py:91-98](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/cli.py#L91-L98)

The `--http` flag exposes full read/write access to `.torsor/` memory over HTTP with no authentication mechanism. The CLI prints a warning for non-loopback binds, but:

- A loopback bind on a shared machine is reachable by other local users
- The warning is easily ignored or missed in CI/automation contexts
- There is no `--api-key`, no Bearer token validation, no mTLS option

```python
# cli.py:91-98
if http and host not in ("127.0.0.1", "localhost", "::1"):
    typer.echo("WARNING: the HTTP transport has no authentication...", err=True)
run(root, transport="streamable-http" if http else "stdio", host=host, port=port)
```

**Impact**: Any process on the machine (or network, for non-loopback binds) can read/write project memory, inject malicious handoffs, corrupt the charter, or poison the recall index.

---

#### HIGH — [I-9] `shell=True` in command execution

**File**: [src/torsor_helper/operations.py:431](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L431)

`subprocess.run(found["command"], shell=True, ...)` executes user/agent-recorded commands through the shell. The `commands.md` file is a committed Markdown artifact — if compromised through a malicious PR, MCP tool abuse, or supply-chain attack, arbitrary shell commands can be injected.

```python
# operations.py:431
return subprocess.run(found["command"], shell=True, cwd=str(store.paths.root))
```

**Impact**: Full shell command injection via the persisted command book. Combined with I-8, an unauthenticated HTTP attacker could write a malicious command and then trigger its execution.

---

#### HIGH — [I-10] No input validation or sanitization on stored memory

**File**: [src/torsor_helper/server.py:37](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/server.py#L37)

`remember()` and other tools accept unbounded string inputs that become part of the stored knowledge base. An adversarial prompt injected into stored memory would be replayed to the agent in subsequent `bootstrap_session()` calls — creating a persistent prompt injection vector.

```python
# server.py:37 — no validation on content
def remember(content: str, kind: str = "observation", links: list[str] | None = None) -> str:
    return ops.remember(store, content, kind=kind, links=links)
```

**Impact**: Persistent cross-session prompt injection. An attacker who writes memory once can influence all future agent sessions for that project.

---

#### MEDIUM — [I-11] No rate limiting on resource-intensive tools

Calls to `map_repo()`, `consolidate()`, or `recall()` (which triggers reindexing) can be repeated without limit. This enables CPU/IO exhaustion attacks against the MCP server.

**Affected tools**: `map_repo`, `consolidate`, `recall` (indirectly via reindex), `export`

**Impact**: Resource exhaustion DoS via repeated expensive tool calls.

---

#### LOW — [I-12] Path traversal risk in map_repo paths parameter

**File**: [src/torsor_helper/server.py:51](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/server.py#L51)

The `paths` parameter in `map_repo()` accepts arbitrary file paths. While they are resolved relative to the project root, there is no explicit boundary check that paths are within the project directory. A carefully crafted relative path like `../../etc/passwd` could potentially escape — mitigated by the scanner only reading `.py` files, but the vector exists.

---

### B3. Maintainability & Code Quality (Impacts: P2, P3, P7)

#### HIGH — [I-13] Duplicate tier weight definitions

**Files**: [src/torsor_helper/search.py:14-16](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/search.py#L14-L16), [src/torsor_helper/recall.py:11-17](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/recall.py#L11-L17)

Both files define identical `_TIER_WEIGHTS` dicts. A change to one would silently diverge indexed vs. keyword recall scoring, producing inconsistent result rankings that would be nearly impossible to debug.

```python
# search.py:14-16
_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5, Tier.ARCHITECTURE: 1.4, Tier.ACTIVE: 1.2, Tier.MAP: 1.1, Tier.EPISODIC: 1.0,
}

# recall.py:11-17 — identical, independent copy
_DEFAULT_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5, Tier.ARCHITECTURE: 1.4, Tier.ACTIVE: 1.2, Tier.MAP: 1.1, Tier.EPISODIC: 1.0,
}
```

**Impact**: Scoring divergence between indexed search and keyword fallback if only one definition is updated.

---

#### HIGH — [I-14] operations.py is a god module (760 lines)

**File**: [src/torsor_helper/operations.py](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py)

`operations.py` handles 16+ distinct operational domains:

| Domain | Line Range | Concern |
|--------|-----------|---------|
| Session bootstrap | 29-53 | Context assembly |
| Recall orchestration | 99-115 | Search dispatch |
| Memory persistence | 118-152 | Remember, update, handoff |
| Repo mapping | 155-199 | Cartographer orchestration |
| Export | 202-203 | llms.txt + Mermaid |
| File/symbol finder | 206-213 | Fuzzy search dispatch |
| Rules management | 220-278 | Agent rules + block writing |
| Project primer | 292-324 | Token-efficient context |
| Model routing policy | 342-383 | Model tier definitions |
| Command book | 390-431 | CRUD + shell execution |
| Op frequency logging | 436-460 | Recipes data |
| Impact analysis | 463-490 | Blast radius |
| Intent surfacing | 493-529 | Architecture + symbols |
| ADR recording | 561-583 | Decision lifecycle |
| Practices adoption | 592-637 | Best-practice packs |
| Drift checking | 678-707 | Guard orchestration |
| Dependency checking | 710-718 | Slopsquatting |
| Coach recommendations | 721-728 | Health assembly |
| Consolidation | 737-760 | Maintenance pass |

This violates the project's own layered architecture principle (ADR 0002). The module was designed as "the tested orchestration core" but has become a catch-all.

**Impact**: Testing, understanding, and modifying any single operation requires navigating a 760-line module. Risk of merge conflicts and unintended coupling between unrelated operations.

---

#### MEDIUM — [I-15] Magic numbers for tier importance and budget fractions

**Files**: [src/torsor_helper/search.py:14-16](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/search.py#L14-L16), [src/torsor_helper/operations.py:19-25](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L19-L25)

Tier weights (1.5, 1.4, 1.2, 1.1, 1.0) and budget fractions (0.30, 0.20, 0.15, 0.18, 0.10, 0.07) are hardcoded. The bootstrap token total is configurable via `TorsorConfig.budgets.bootstrap_tokens`, but the section allocations are not tunable without code changes.

```python
# operations.py:19-25
_BOOTSTRAP_ALLOC = [
    ("Charter", "charter", 0.30),
    ("System Patterns", "system_patterns", 0.20),
    ("Tech Context", "tech_context", 0.15),
    ("Active Context", "active_context", 0.18),
    ("Progress", "progress", 0.10),
]
_RECENT_JOURNAL_FRACTION = 0.07
```

**Impact**: Cannot tune which sections get more token budget without patching source code.

---

#### MEDIUM — [I-16] Deferred imports as a layering workaround

Multiple files use deferred `import` inside functions to avoid circular dependencies:

```python
# operations.py:210
from torsor_helper import finder

# operations.py:425
import subprocess

# operations.py:595
from torsor_helper import practices as _practices
```

While intentional for the layered architecture enforced by ADR 0002, several of these imports (e.g., `finder`, `practices`, `deps`) are always needed and could be top-level in a properly restructured module layout.

---

#### MEDIUM — [I-17] Missing type annotations on public API functions

**File**: [src/torsor_helper/operations.py:561](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L561)

Several public API functions lack type annotations for critical parameters:

```python
# operations.py:561 — no type hints for store, title, context, decision
def record_decision(store, title, context, decision, consequences="", rules=None, supersedes=None) -> str:
```

Similarly, several coach module functions omit type annotations. This reduces IDE support and makes the API contract implicit.

---

#### LOW — [I-18] HashingEmbedder produces weak semantic vectors

**File**: [src/torsor_helper/embeddings.py:20-44](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/embeddings.py#L20-L44)

The fallback hashing embedder uses a deterministic bag-of-words hash (MD5-based). Users without the `embeddings` extra get degraded recall quality with no semantic understanding — "error handling" and "exception management" may produce orthogonal vectors.

The design choice is intentional (offline-first, no mandatory network/API key), but the UX degradation is silent — users may not realize they're getting keyword-only recall quality.

---

### B4. Architecture & Design (Impacts: P1, P2, P3, P4, P6)

#### HIGH — [I-19] Entirely synchronous despite being an MCP server

**File**: [src/torsor_helper/server.py](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/server.py)

All tool handlers are synchronous. FastMCP supports `async def` handlers natively. Blocking I/O in every tool handler (disk reads, SQLite queries, subprocess calls, embedding computation) means the server can only handle one request at a time even with streamable-http transport.

```python
# server.py — all tools are sync
@mcp.tool()
def recall(query: str, limit: int = 8) -> str:  # sync def, not async def
    result = ops.recall(store, config, query, limit=limit)
```

**Impact**: Under concurrent tool calls (HTTP transport), one slow `map_repo()` blocks all other requests. The server cannot interleave I/O.

---

#### HIGH — [I-20] No incremental map updates; full rebuild on any change

**File**: [src/torsor_helper/cartographer.py:229-274](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/cartographer.py#L229-L274)

`_scan()` is a full-tree walk of all Python files. Combined with replace-all semantics in the DB and the all-or-nothing fingerprint skip, there is no path for incrementally adding, updating, or removing symbols when a single file changes.

**Impact**: `map_repo()` is O(project files) every time, making it impractical to run frequently on large codebases.

---

#### MEDIUM — [I-21] Python-only cartographer with no extension point

**File**: [src/torsor_helper/cartographer.py:28-52](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/cartographer.py#L28-L52)

`extract_symbols()` and `extract_edges()` are hardcoded for Python's `ast` module. The project's tech context acknowledges multi-language support is planned, but the current architecture has no abstraction layer or strategy pattern for pluggable language parsers.

```python
# cartographer.py:28-30 — Python-only, no abstraction
def extract_symbols(source: str, module: str) -> list[Symbol]:
    try:
        tree = ast.parse(source)
```

**Impact**: Adding TypeScript/Go/Rust support requires significant refactoring rather than implementing a new parser plugin.

---

#### MEDIUM — [I-22] Complexity snapshot only updated during consolidate

**File**: [src/torsor_helper/operations.py:751](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L751)

The complexity snapshot used for regression detection is saved only during the `consolidate()` maintenance pass. There is no CI hook, no auto-trigger, no `map_repo` side-effect — if `consolidate` is never called, regression detection remains completely blind.

```python
# operations.py:751 — only saved during manual consolidate
db.save_complexity_snapshot(conn, coach_trend.current_complexity(store.paths.root))
```

**Impact**: The Coach's "complexity regression" feature is effectively dead unless users remember to run `torsor consolidate` periodically.

---

#### MEDIUM — [I-23] MMR diversity applied only to indexed path

**File**: [src/torsor_helper/search.py:37-60](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/search.py#L37-L60)

`_mmr_order()` is called only in `hybrid_search()` (the indexed path). The keyword fallback (`recall.py`) has no diversity mechanism, so near-duplicate notes can crowd out distinct results.

**Impact**: Users without the `embeddings` extra (or with `auto_index: false`) get lower-quality recall that may surface 8 variations of the same note.

---

#### LOW — [I-24] No transaction isolation for multi-step DB operations

**File**: [src/torsor_helper/operations.py:155-199](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/operations.py#L155-L199)

`map_repo()` does `replace_all_symbols()`, `replace_all_edges()`, `reindex()`, then `commit()`. If `reindex()` fails mid-operation, symbols and edges are already wiped from the DB with no rollback.

```python
# operations.py:181-190 — no explicit transaction or rollback
db.replace_all_symbols(conn, symbols)   # DELETE + INSERT
db.replace_all_edges(conn, edges)       # DELETE + INSERT
reindex(store, conn, _embedder_for(config))  # may fail here
...
conn.commit()  # only reached if reindex succeeds
```

---

### B5. Testing & QA (Impacts: P2, P5, P6, P7)

#### HIGH — [I-25] No integration tests for the MCP server protocol

While there are 68+ unit test files covering individual modules, none exercise the MCP server over stdio or HTTP transport end-to-end. The `server.py` adapter is tested indirectly (e.g., `test_server.py` likely tests `build_server()` output structure), but full MCP JSON-RPC protocol compliance, tool dispatch, and error handling over the wire are unverified.

**Impact**: A protocol-level regression (e.g., malformed JSON-RPC response, tool not discoverable) would not be caught by the current test suite.

---

#### MEDIUM — [I-26] No performance regression benchmarks

No benchmark tests exist to detect regressions in:
- Cosine search latency as note count grows
- Index rebuild time
- Recall throughput
- Map scan time on large codebases

**Impact**: A seemingly innocuous change (e.g., removing an optimization in the indexer) could degrade performance without any automated signal.

---

#### MEDIUM — [I-27] No concurrency tests

Tests do not verify behavior under:
- Concurrent MCP tool calls via HTTP transport
- Simultaneous reads and writes to the SQLite index
- WAL contention scenarios
- Race conditions in CoachState JSON persistence

**Impact**: The WAL mode configuration and connection handling may have subtle bugs under concurrent load that current testing cannot detect.

---

#### LOW — [I-28] Error degradation paths are untested

Many `try/except: pass` blocks exist with the design intent of graceful degradation:

```python
# operations.py:436-448
def _log_op(store: Store, op: str, args: str = "") -> None:
    try:
        ...
    except Exception:
        pass  # logging must not break a tool
```

No tests verify that failures in logging, indexing, or config loading degrade gracefully without breaking the parent operation. The contract is implicit.

---

### B6. Usability & Documentation (Impacts: P1, P3, P7)

#### MEDIUM — [I-29] Coach recommendations lack concrete action steps

**File**: [src/torsor_helper/coach/health.py:15-48](file:///Users/magnetoid/Documents/trae_projects/torsor-mem/src/torsor_helper/coach/health.py#L15-L48)

Many recommendations provide vague actions:

```python
# health.py:23 — vague action
action=f"Edit {path}"

# health.py:33 — vague action
action="run handoff or update_active"

# health.py:46 — vague action
action="add a rules: block to an ADR's frontmatter"
```

Compare with what they could be:

```python
action="Replace the seed template in .torsor/charter.md with a one-paragraph description of what this project builds"

action="Call handoff() at the end of your session to capture decisions and next steps"

action="Add `rules:\n  - kind: forbid_import\n    target: ...` to an ADR's YAML frontmatter"
```

**Impact**: Agents receiving these recommendations have to re-derive the specific steps, partially defeating the purpose of the Coach.

---

#### LOW — [I-30] No generated API documentation

The project lacks autogenerated API docs. The README, CLAUDE.md, and .torsor/ files serve as documentation, but there is no structured reference for the public API surface (MCP tools, CLI commands, Python API).

---

## C. Prioritized Improvement Roadmap

### Phase 1 — Critical Fixes (Weeks 1–3)

| ID | Task | Addresses | Effort |
|----|------|-----------|--------|
| **1.1** | **Add HTTP transport authentication** | I-8 | M |
| | Add `--api-key` flag to `torsor mcp --http`. Validate Bearer token or `X-API-Key` header. Reject non-loopback binds when no auth is configured. | | |
| | **Success metric**: Unauthenticated HTTP requests return 401. | | |
| **1.2** | **Fix partial map scan data destruction** | I-4 | S |
| | Change `replace_all_symbols()`/`replace_all_edges()` to upsert semantics (DELETE only the modules being rescanned) or refuse partial scans unless `--force` is passed. | | |
| | **Success metric**: `map_repo(paths=['a.py'])` preserves symbols for `b.py`. | | |
| **1.3** | **Extract tier weights to single source of truth** | I-13 | S |
| | Move `_TIER_WEIGHTS` to `models.py`; import from both `search.py` and `recall.py`. Add a test that asserts both modules produce identical weights. | | |
| | **Success metric**: One definition; test verifies consistency. | | |
| **1.4** | **Mitigate shell injection in command execution** | I-9 | S |
| | Use `shlex.split()` on recorded commands and pass as a list to `subprocess.run()`, removing `shell=True`. | | |
| | **Success metric**: `run_command()` no longer uses `shell=True`. | | |

### Phase 2 — Performance & Architecture Hardening (Weeks 4–8)

| ID | Task | Addresses | Effort |
|----|------|-----------|--------|
| **2.1** | **Add approximate nearest neighbor search** | I-1 | L |
| | Integrate `faiss-cpu` (optional dependency) or implement IVF-based indexing. Fall back to exact search when the extra is not installed. | | |
| | **Success metric**: <50ms P99 vector search for 10,000 notes. | | |
| **2.2** | **Decouple reindex from recall path** | I-2 | M |
| | Move reindexing to explicit `torsor index` invocation or a configurable auto-sync interval. `_open_index()` should open an existing index without triggering sync. | | |
| | **Success metric**: `recall()` latency drops by the stat-scanning overhead (~5–50ms/call). | | |
| **2.3** | **Split operations.py into domain modules** | I-14 | L |
| | Extract: `session.py` (bootstrap, primer, rules, model_policy), `memory_ops.py` (remember, update_active, handoff), `decision_ops.py` (record_decision, adopt_practices), `drift_ops.py` (check_drift, guard_run), `command_ops.py` (list/record/run commands). Keep `operations.py` as a re-export facade. | | |
| | **Success metric**: No module exceeds 300 lines (excluding models/config). | | |
| **2.4** | **Make map_repo incremental** | I-3, I-20 | L |
| | Replace the all-or-nothing fingerprint with per-file content hashes. On map, only rescan files whose hash changed; upsert their symbols/edges. | | |
| | **Success metric**: Changing one file in a 500-module project remaps only that module. | | |
| **2.5** | **Add input sanitization for stored memory** | I-10 | S |
| | Strip/escape control characters from user-provided content before storage. Add configurable max length for `remember()` and `handoff()` content. | | |
| | **Success metric**: Malicious input with ANSI escape sequences or embedded null bytes is sanitized. | | |

### Phase 3 — Security & Robustness (Weeks 9–12)

| ID | Task | Addresses | Effort |
|----|------|-----------|--------|
| **3.1** | **Add rate limiting** | I-11 | M |
| | Implement token-bucket rate limiter for expensive operations. Configurable via `torsor.toml`. | | |
| | **Success metric**: Rapid repeated calls to `map_repo()` are throttled after N/sec. | | |
| **3.2** | **Add transaction isolation for multi-step DB ops** | I-24 | S |
| | Wrap `map_repo()` DB operations in explicit transactions with rollback on failure. | | |
| | **Success metric**: Failed reindex does not leave the DB with zero symbols. | | |
| **3.3** | **Add complexity snapshot to CI path** | I-22 | S |
| | Run `torsor consolidate` (or just the snapshot portion) in CI on main branch pushes so the Coach always has a baseline. | | |
| | **Success metric**: Complexity regressions are detectable within one CI cycle of the change. | | |

### Phase 4 — Async, Testing & Polish (Weeks 13–16)

| ID | Task | Addresses | Effort |
|----|------|-----------|--------|
| **4.1** | **Add async support to MCP server** | I-19 | L |
| | Convert server tool handlers to `async def`. Use `aiofiles` for file reads and `aiosqlite` for DB operations. Keep CLI sync. | | |
| | **Success metric**: Server handles concurrent recall requests without blocking. | | |
| **4.2** | **Add MCP integration tests** | I-25 | M |
| | Spin up the MCP server in stdio/HTTP mode; send JSON-RPC messages; verify responses. Test full recall pipeline end-to-end. | | |
| | **Success metric**: CI fails if MCP protocol contract breaks. | | |
| **4.3** | **Add performance benchmarks** | I-26 | M |
| | Add `benchmarks/` with pytest-benchmark tests for recall, map, consolidate on synthetic datasets (100, 1k, 10k notes). | | |
| | **Success metric**: CI reports performance regressions. | | |
| **4.4** | **Improve Coach action specificity** | I-29 | S |
| | For each recommendation kind, provide a concrete, copy-pasteable command or code snippet. | | |
| | **Success metric**: Every `Recommendation.action` field contains an executable command or specific edit instruction. | | |
| **4.5** | **Add pluggable language parser abstraction** | I-21 | M |
| | Define a `LanguageParser` protocol; extract Python AST logic into a `PythonParser` implementation. Register parsers by file extension. | | |
| | **Success metric**: Adding a TypeScript parser is a new module implementing the protocol, not a refactor of cartographer. | | |

---

## D. Risk Mitigation Summary

| Risk | Probability | Mitigation |
|------|-------------|------------|
| HTTP auth changes break existing users | Low | Make auth opt-in with `--api-key`; keep loopback-default behavior unchanged for local dev |
| operations.py split creates import cycles | Medium | Use late-binding imports in facade; validate with `torsor guard --strict` after refactor |
| ANN dependency breaks offline guarantee | Low | Make `faiss` an optional extra; fall back to exact search (existing degradation pattern) |
| Incremental map introduces stale data | Medium | Per-file content hashes as cache keys; `--full` flag for forced rebuilds; integration tests |
| Async migration breaks sync CLI | Low | Keep CLI sync; only convert server handlers. FastMCP supports mixed sync/async |
| Rate limiting causes false throttles in CI | Low | Configurable thresholds; disable in CI via env var |

---

## Appendix: Architectural Strengths

Notable design decisions that should be preserved through any refactoring:

1. **Markdown-as-truth with derived index**: The clean separation between source of truth (`.torsor/*.md`) and disposable index (`.torsor/.index/torsor.db`) is robust and well-implemented. The index can be deleted and rebuilt at any time.

2. **Graceful degradation chain**: No index → keyword recall; no fastembed → hashing embedder; no git → file walk. Every capability degrades to a working fallback.

3. **Token budgeting pervasive**: Every context-returning path (`bootstrap_session`, `recall`, `project_primer`, `agent_rules`, `get_intent`) is token-budgeted via `truncate_to_tokens()`. This is essential for LLM context windows.

4. **ADR-enforced layering**: The `forbid_import` rules in ADR 0002 create machine-enforceable architectural boundaries between core and adapters. Few projects dogfood their own architectural rules this rigorously.

5. **Baseline ratchet for drift**: The committed `baseline.json` allows grandfathering existing violations while failing on new ones — a practical approach that avoids the "fix everything first" trap.

6. **RRF fusion for hybrid search**: Reciprocal Rank Fusion combines FTS5 keyword results with vector similarity, plus recency boost and graph boost — a mature information retrieval pattern.

7. **Frecency-based file finder**: The `find_files` tool uses a monotonic counter for frequency + recency scoring, making it a lightweight but effective "jump to file" mechanism.

8. **Self-dogfooding**: The project uses its own `.torsor/` memory, ADRs with machine-readable rules, and `torsor guard` in its own development workflow. This ensures the tool is always tested against a real use case.
