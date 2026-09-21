---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-09-21T13:00:00'
updated: '2026-09-21T13:00:00'
rules: []
---

# ADR 0016: Note→symbol mentions are extracted unfiltered and joined at query time

## Context
torsor already keeps two graphs and never connected them. `edges` links a note to a note (wiki links), and `symbol_edges` links code to code — so `impact` could say what calls `norm_path` and nothing could say what the team *decided* about it. That second question is the one this architecture is uniquely able to answer, because the decisions and the symbol table live in the same index, and it did not ship. An agent about to change a function could see every caller and none of the recorded intent.

The obvious implementation is to extract backticked identifiers from each note while indexing and keep the ones that match a row in `symbols`. That filter is a trap. `reindex` screens on `(mtime, size)` and never re-reads an unchanged note, so a note written before the first `torsor map` would be scanned once, find no symbol table, record nothing, and never be looked at again. The feature would work for notes written after the map and silently not for notes written before it — which is most of them, since memory precedes the map on every project.

## Decision
Extraction is deliberately dumb and the join happens at query time. `store.extract_symbol_mentions` keeps every backticked token that reads like an identifier, and `db.note_symbols` stores it whether or not a symbol by that name exists. Whether a mention names real code is decided when someone asks, by looking the symbol up — so the note index and the symbol map can be built in either order, any number of times, and the answer is the same.

Three narrowings, each for a reason. Fenced code blocks are stripped, because a code sample is an illustration rather than a claim about a symbol. A token must look like an identifier, so `--json` and `torsor map --force` are not mentions. And **map notes contribute nothing**: they are rendered *from* the symbol table, so their mentions are that table restated — by far the largest source of rows and the only one carrying no information. What the feature is for is authored memory: decisions, learnings, handoffs.

A dotted `ops.recall` records both itself and `recall`, because a note may use either spelling and the symbol table may hold either.

The mention table gets its own format stamp (`MENTIONS_FORMAT_VERSION`), separate from both `SCHEMA_VERSION` and `INDEX_FORMAT_VERSION`. Adding it to `INDEX_FORMAT_VERSION` would have worked and would have re-embedded every note in the corpus to populate a regex result; instead a one-time backfill reads each note the stat pre-screen skipped and fills the table without touching a vector.

This surfaces in three places: `impact` gains the notes that mention the symbol alongside the code that calls it, `get_intent` gains what was recorded about the topic (including journals, which its ADR-title list never reaches), and `recall` gains `symbol=`.

## Consequences
"What did we decide about this function?" is now one call, and `impact` answers the question an agent actually has before a refactor — callers *and* recorded intent — rather than half of it. The two halves are independent, so a symbol nothing calls can still be the one the team argued about, and that case renders correctly.

Costs. The table holds tokens that name nothing, which is wasted rows in exchange for order-independence; the per-note cap (200) bounds the worst case. Extraction is lexical, so it has both kinds of error: a note that discusses a function in prose without backticks is invisible, and a backticked word that happens to match a symbol name is a false link. Precision over recall was not available here the way it was for staleness (ADR 0010) — this output is advisory context, not a gate, so a stray link costs a line and a missed one costs nothing that was not already missing.

No machine-checkable rule accompanies this ADR. The invariants that matter — extraction never consults the symbols table, map notes contribute nothing, the backfill never re-embeds — are behavioural, and a `forbid_pattern` proxy for any of them would be decoration. `tests/test_note_symbols.py` asserts each one directly, including the ordering case that motivated the whole design.
