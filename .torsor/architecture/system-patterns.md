---
type: system-patterns
status: active
tags: [architecture]
---

# System Patterns

## Architecture overview
Layered: pure core (models, budget, store, paths, config, recall, embeddings, db,
cartographer, guard, operations) under thin adapters (server = FastMCP, cli = Typer).
Adapters depend on core; core never imports adapters.

## Conventions
- TDD: failing test first, minimal implementation, frequent commits.
- Pure modules use stdlib where possible (ast cartographer; no tree-sitter).
- Every context-returning path is token-budgeted.
- Errors degrade gracefully (no index -> keyword recall; no fastembed -> hashing).

## Patterns in use
- Markdown + YAML frontmatter + wikilinks; derived SQLite index (FTS5 + vectors + edges).
- ADRs carry machine-readable `rules:` consumed by the drift guard.
