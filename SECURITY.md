# Security

## Reporting

Email **marko.tiosavljevic@gmail.com** with "torsor-helper security" in the
subject. Please do not open a public issue for anything exploitable. I will
acknowledge within a week.

## What torsor does that is worth knowing about

torsor is local-first and offline: it never calls a model, never phones home,
and needs no API key. The things worth understanding before you run it:

**The HTTP transport has no authentication.** `torsor mcp --http` serves read
*and write* access to a project's memory to anyone who can reach the port. It
binds loopback by default and refuses a routable interface unless you pass
`--allow-remote`. If you use it, put it behind a reverse proxy or an SSH
tunnel. Do not expose it.

**Recorded commands run in a shell.** `.torsor/commands.md` is committed, so a
pull request can change what `torsor commands --run test` executes. Command
execution is CLI-only for this reason — no MCP tool can reach it — but read a
diff to that file the way you would read a diff to a CI config.

**Installed hooks run `torsor` from your PATH.** `torsor hooks install` writes
entries into `.git/hooks` and `.claude/settings.json`. The latter is usually
committed, so every collaborator's session runs whatever binary named `torsor`
their PATH resolves. That is the same trust model as a `Makefile` or a
`.pre-commit-config.yaml`, but it is worth stating.

**Paths from a tool call are contained.** `check_drift` and `verify` take a
file list over MCP, so a prompt-injected agent could pass anything; every
caller-supplied path is resolved and rejected if it lands outside the project
root, symlinks included.

**`torsor update` replaces the running binary.** It shows the command and asks
before running, and there is no signature check — it trusts your package index
exactly as much as `pip install` does.

## Scope

Anything that lets a repository, a tool call or a note read or write outside
the project root, or execute code the user did not ask for, is a bug. Report it.
