---
type: tech-context
status: active
tags: [architecture]
---

# Tech Context

## Stack & versions
Python >=3.11. FastMCP (mcp), Typer, Pydantic v2, PyYAML, tomli-w, SQLite (FTS5),
NumPy (cosine). Optional: fastembed (semantic embeddings). Dev: pytest, anyio, ruff.

## Constraints
- No mandatory network/API key on the default path.
- Vector search is BLOB float32 + NumPy cosine (portable), not sqlite-vec.
- The repo map is Python-only (stdlib ast); multi-language is planned.
