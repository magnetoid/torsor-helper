---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-09-21T15:00:00'
updated: '2026-09-21T15:00:00'
rules:
- kind: forbid_import
  target: torsor_helper.embeddings
  scope: src/torsor_helper/coach/contradiction.py
  severity: error
  message: "contradiction detection is lexical on purpose — the default embedder is the hashing fallback, which fabricates similarity (ADR 0017)"
---

# ADR 0017: Recommendations have a lifecycle, and contradiction detection is lexical

## Context
Two gaps left over from the Coach spec, and they turn out to share a shape: both are about a problem that is invisible while it exists.

The Coach tracked only `dismissed` and `times_shown`. `times_shown` drives a deliberate decay — a recommendation seen many times sinks within its severity band so the Coach never nags — but nothing ever noticed the opposite. A recommendation you *fixed* simply stopped appearing, indistinguishable from one that sank below the limit or one you were never shown. So the Coach could never say "you fixed three things", and an unaddressed problem had no age: "your charter is still the seed template" read the same on day one and day ninety.

Separately, nothing checked whether two active decisions disagree. This is the specific way a growing ADR set rots: a decision is reversed in a new ADR and the old one is never marked `superseded`, so `torsor guard` enforces one rule while `get_intent` hands the agent the other. Both notes are individually well-formed, so no existing check can see it.

## Decision
**Lifecycle.** `CoachState` gains `first_seen` and `last_shown`, and a `resolve_missing(present)` sweep: keys that were shown before, are not dismissed, and are no longer produced were fixed. They are reported once as a single `kind="resolved"` recommendation and then forgotten.

Three constraints, each of which is a way to lie if you get it wrong. Resolution compares against *everything computed this run*, before the page is truncated — otherwise raising `limit` would "fix" things and lowering it would un-fix them. A key that was never shown is never resolved, because it was never surfaced, so no one fixed it. And `session_digest` does not sweep at all: it runs three index-free checks, so a key it does not produce is absent because it was not looked for, and sweeping there would mark every hotspot fixed at the start of every session.

The `resolved` recommendation excludes its own key from the sweep. Without that the regress is infinite: it is shown, it is absent next run, and it reports that the report was fixed, forever.

**Escalation adds information, not position.** After three showings and seven days, an `important` recommendation says how long it has been open. It is not re-ranked, because rank is what the decay controls and escalating by rank would quietly reverse a decision that is already load-bearing.

**Contradiction detection is lexical.** The spec called for near-duplicate embedding vectors plus opposite polarity. That was rejected on evidence: torsor's default embedder is the hashing fallback, 384 md5 buckets with no IDF, and Phase 2 measured what it does under a similarity threshold — it *fabricates* matches, because every text has some similarity to every other. A check that fires on nothing real is worse than no check. Term overlap on decision titles means the same thing on every install, with or without the `embeddings` extra, and a guard rule keeps the embedder out of this module so the next person does not helpfully add it back.

Polarity is a sign, not a score: negatives win over positives, because "never use X" contains "use" and the prohibition is the claim. A pair is flagged only when both titles carry at least three topic words, overlap by 0.55 Jaccard, and have opposite polarity. An explicit `supersedes` link or `status: superseded` exempts the pair, because that is how a decision is *meant* to be reversed.

Precision over recall, as ADR 0010 requires of anything advisory. The thresholds are set against this repo's own ADRs, which do not contradict each other, and a test asserts the check finds nothing in them: firing on a set known to be consistent is wrong, not sensitive.

## Consequences
The Coach can now say what improved, which is the one thing it could never do — and an old `important` recommendation carries its own age, so "still the seed template" stops reading identically forever. The pair-key is order-independent, so dismissing a contradiction sticks whichever way round the two notes are compared next time.

Costs. Resolution depends on state that is machine-local and git-ignored, so a fresh clone reports nothing as fixed and a deleted `.torsor/state/` loses the history — acceptable, because the cost of losing it is one missed piece of good news. The sweep also deletes state entries, so a recommendation that disappears and comes back is "new" again and its age resets; that is the honest reading, since the problem did go away.

Contradiction detection will miss most real contradictions. Two decisions that disagree in their bodies while their titles differ are invisible, and so is any disagreement expressed without one of the polarity words. That is the deliberate direction to be wrong in: this surfaces to a human as advice, and an advisory check nobody trusts is one nobody reads.
