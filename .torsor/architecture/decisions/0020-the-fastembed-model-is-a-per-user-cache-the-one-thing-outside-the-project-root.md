---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-11-19T00:00:00'
updated: '2026-11-19T00:00:00'
rules: []
---

# ADR 0020: The fastembed model is a per-user cache, the one thing outside the project root

## Context
torsor keeps everything under the project root, so `.torsor/` travels with the repo and dies with
it. fastembed never followed that rule: given no `cache_dir`, it stores its model under
`tempfile.gettempdir()/fastembed_cache`. The OS clears that directory. The next process downloads the
model again (measured: 32 s for BAAI/bge-small-en-v1.5), and an offline one falls back to the
hashing embedder, so recall quality quietly changes with the state of `/tmp`.

Moving the model into the project (`.torsor/.index/models/`) would follow the rule to the letter, but it costs
~130 MB per project. `torsor clean --deep` removes `.index/` wholesale, so the next recall would
download the model again, which is the same failure.

## Decision
The fastembed model lives in a **per-user cache**: `$FASTEMBED_CACHE_PATH` if set, else
`$XDG_CACHE_HOME/torsor-helper/fastembed`, else `~/.cache/torsor-helper/fastembed`
(`embeddings.model_cache_dir`). It is passed to fastembed explicitly as `cache_dir`.

The project-root rule is about project **state**: memory, the index, Coach dismissals. A
model's weights are a download that is the same for every project and holds nothing about any of
them. They are the only exception. Anything that describes or derives from a project still
belongs under its root.

## Consequences
- One download per machine instead of one per temp-dir cleanup. Projects share it.
- Deleting a project or running `clean --deep` leaves the model in place. Removing it is
  `rm -rf ~/.cache/torsor-helper`.
- A user who already set `FASTEMBED_CACHE_PATH` keeps that location unchanged.
