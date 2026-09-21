---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-09-21T11:00:00'
updated: '2026-09-21T11:00:00'
rules:
- kind: forbid_pattern
  target: register_driver
  scope: src/torsor_helper/server.py
  severity: error
  message: "registering a merge driver writes to .git/config — a local machine mutation, so it is CLI-only like the hook installers (ADR 0009, ADR 0015)"
---

# ADR 0015: Team memory merges through committed attributes and a per-clone driver

## Context
`.torsor/` is committed Markdown, which is what makes it team memory rather than one developer's cache — and also what makes two branches collide. Two people working the same day both append to `memory/journal/<date>.md`, and `auto_map_on_commit` makes every commit regenerate notes under `map/`, so any two branches that touched code conflict across dozens of map notes. Neither conflict deserves a human: journal entries are an append-only log where both sides are wanted, and map notes are *derived*, so the correct resolution is to discard both sides and re-run the mapper. Left alone, this is the failure that stops a team from committing `.torsor/` at all, which turns shared memory back into a local one.

Git offers exactly one distributable mechanism — a committed `.gitattributes` — and it can only name the built-in merge drivers (`text`, `binary`, `union`). Anything smarter needs a `merge.<name>.driver` entry in `.git/config`, which is per-clone and cannot be committed. Worse, git does **not** warn when an attributes file names a driver the clone has not registered: it silently falls back to the normal text merge. A team that believes it is configured and is not gets exactly the behaviour it had before, with no diagnostic.

## Decision
Two halves, deliberately separated by what git can and cannot distribute.

**Committed:** `torsor init` writes `.torsor/.gitattributes` with a managed block (foreign lines preserved). `memory/journal/*.md` gets `merge=union`, which is built in and therefore works in every clone with no setup at all. `map/**` gets `merge=torsor-map`.

For the union merge to be safe, the journal *header* must be identical on both sides, or union merges the frontmatter too and leaves a duplicate `created:`/`updated:` pair inside the `---` block on every merge. So `store.append_journal` stamps a journal with its own date at midnight rather than the wall clock — which is also the truer value, since the stamp was never refreshed on append and only ever meant "this day". The clock still names each entry (`## HH:MM · kind`), where it belongs.

**Per-clone:** `torsor merge install` registers `merge.torsor-map.driver` in `.git/config`. The driver keeps our version, records the path in `.torsor/state/merge_regen.json`, and exits 0; `torsor map --force` regenerates those notes from source and clears the queue. It does not attempt a content merge, and it does not regenerate in place — the source file may itself be mid-conflict at that moment, and the order git invokes drivers in is unspecified. A driver that cannot run at all exits non-zero, which git reads as "conflict": the safe direction to fail in, since the user then sees markers instead of a silently discarded change.

Registering the driver writes to `.git/config`, which is a mutation of the developer's machine rather than of the project, so it is CLI-only — the same rule as the hook installers (ADR 0009) and machine-checked the same way. Because the second half is invisible when it is missing, `torsor merge status` and a `doctor` check both report an attributes file whose driver this clone has not registered.

`memory.journal_partition = "date-author"` is the escape hatch for teams large enough that union merges get noisy: each git identity gets `<date>.<author>.md` and concurrent work never touches the same path. The date stays the leading token because `clean` reads the retention date straight out of the filename stem.

## Consequences
A team can commit `.torsor/` and keep it. Journals merge with no configuration whatsoever — the single most common conflict is solved by the committed half alone. Map notes stop conflicting once each developer runs `torsor merge install`, which is one command and is what `doctor` tells them to run.

Costs. The split is genuinely confusing: half the configuration is in git and half is not, and only the half that is not can be forgotten. A `map/**` merge always resolves to ours, even when it would have merged cleanly, so a map note is briefly wrong between the merge and the next full map — acceptable only because the note is derived and the post-commit hook remaps. `merge=union` will duplicate an entry that reaches both branches (a cherry-pick, a rebase); `torsor consolidate` already detects and reports duplicate journal entries, so the recovery exists. `memory/insights/` is deliberately left on git's normal text merge: both sides append bullets to a list with a common ancestor, which three-way merges correctly, and `consolidate` regenerates them anyway. And this buys nothing for `active/*.md`, which is hand-written prose that a text merge handles as well as anything could.
