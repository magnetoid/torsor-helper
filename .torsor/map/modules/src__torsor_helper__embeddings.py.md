---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/embeddings.py

Symbols in `src/torsor_helper/embeddings.py`.

- L13 `Embedder` (class)
- L17 `embed(self, texts: Sequence[str])` (method)
- L20 `HashingEmbedder` (class) — Deterministic, dependency-free bag-of-words hashing embedder.
- L29 `__init__(self, dim: int=384)` (method)
- L32 `embed(self, texts: Sequence[str])` (method)
- L47 `FastEmbedEmbedder` (class) — Local ONNX embeddings via the optional `fastembed` extra (lazy-loaded).
- L52 `__init__(self, model: str)` (method)
- L58 `embed(self, texts: Sequence[str])` (method)
- L62 `_make_fastembed(model: str)` (function)
- L68 `get_embedder(config)` (function)
