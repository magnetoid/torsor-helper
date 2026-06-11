"""Curated best-practice packs per language.

Each pack distills the *consensus* practices for a language — the overlap of
major style guides and default linter rules (PEP 8/ruff/pylint/bandit, ESLint
recommended, go vet, clippy), weighted toward mistakes AI coding agents are
empirically prone to. Practices that a per-line regex can catch reliably carry
a machine-readable guard rule; the rest are prose principles recorded in the
ADR body. Adopting a pack records ONE ADR whose rules `torsor guard` enforces.

Severity policy: `error` only for near-zero-false-positive patterns; rules
with known false-positive modes ship as `warning`/`hint` so `--strict
--severity error` stays trustworthy, and the committed baseline ratchet
absorbs pre-existing debt.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from torsor_helper.cartographer import DEFAULT_IGNORE

# ---------------------------------------------------------------------------
# Pack data. `rule` is a guard-rule dict (kind/target/scope/severity/message)
# or None for prose-only principles. `ai_prone` marks practices AI-generated
# code is documented to violate often (cited in the ADR body).
# ---------------------------------------------------------------------------

_PYTHON = [
    {
        "title": "No bare `except:` / silently swallowed exceptions",
        "rationale": "Bare except catches SystemExit/KeyboardInterrupt and hides bugs; "
                     "swallowed errors surface far from their root cause (PEP 8; ruff E722; "
                     "the best-documented LLM antipattern).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"^\s*except\s*:",
                 "severity": "error", "message": "bare `except:` — catch a specific exception"},
    },
    {
        "title": "No wildcard imports",
        "rationale": "`from x import *` defeats static analysis and hides provenance (PEP 8; pyflakes F403).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"^\s*from\s+[\w.]+\s+import\s+\*",
                 "severity": "error", "message": "wildcard import — import names explicitly"},
    },
    {
        "title": "No `shell=True` / `os.system`",
        "rationale": "Shell injection (CWE-78 is among the top AI-code CWEs); the list-args "
                     "form of subprocess is always available (bandit B602/B605).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"shell\s*=\s*True|os\.system\(",
                 "severity": "error", "message": "shell injection risk — use subprocess with a list of args"},
    },
    {
        "title": "No `eval`/`exec`",
        "rationale": "Arbitrary code execution; `ast.literal_eval` covers the legitimate case "
                     "(bandit B102/B307). Method calls like `model.eval()` are excluded.",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"(?<![\w.])(eval|exec)\s*\(",
                 "severity": "error", "message": "eval/exec — use ast.literal_eval or refactor"},
    },
    {
        "title": "No mutable default arguments",
        "rationale": "The default is created once at def-time and shared across calls "
                     "(flake8-bugbear B006; pylint W0102). Multi-line signatures escape the "
                     "regex — treat the principle as binding anyway.",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern",
                 "target": r"def\s+\w+\([^)]*=\s*(\[\]|\{\}|list\(\)|dict\(\)|set\(\))",
                 "severity": "warning", "message": "mutable default argument — default to None and create inside"},
    },
    {
        "title": "No pickle / unsafe yaml.load on untrusted data",
        "rationale": "Deserializing untrusted bytes is remote code execution; AI code is ~1.8x "
                     "more likely to use insecure deserialization (bandit B301/B506).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"pickle\.loads?\(|yaml\.load\((?!.*Loader)",
                 "severity": "warning", "message": "unsafe deserialization — use json/safe_load, or justify and baseline"},
    },
    {
        "title": "Always pass `timeout=` to requests calls",
        "rationale": "`requests` has no default timeout — production code hangs forever "
                     "(bandit B113). AI reproduces the ubiquitous timeout-less snippet.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"requests\.(get|post|put|patch|delete|head|request)\((?!.*timeout\s*=)",
                 "severity": "warning", "message": "requests call without timeout="},
    },
    {
        "title": "No hardcoded secrets",
        "rationale": "Copilot-era repos leak ~40% more secrets (GitGuardian). Use env vars or a "
                     "secret manager; placeholders in tests will need baselining.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"(?i)(api_key|apikey|secret|passwd|password|token)\s*=\s*[\"'][A-Za-z0-9_\-/+]{8,}[\"']",
                 "severity": "warning", "message": "possible hardcoded secret — load from the environment"},
    },
    {
        "title": "Use context managers for resources",
        "rationale": "`with open(...)` guarantees release on exception paths (pylint R1732; ruff SIM115).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"^\s*\w+\s*=\s*open\(",
                 "severity": "hint", "message": "prefer `with open(...) as f:`"},
    },
    {
        "title": "Prefer f-strings; logging keeps lazy %-style",
        "rationale": "f-strings are the modern consensus (ruff UP032), but `logger.info(\"%s\", v)` "
                     "lazy formatting is correct in logging calls — only `.format()` is flagged.",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"\.format\(",
                 "severity": "hint", "message": "prefer an f-string over .format()"},
    },
    {
        "title": "Prefer pathlib over os.path",
        "rationale": "Object-oriented, cross-platform path handling (ruff PTH rules).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern",
                 "target": r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\(",
                 "severity": "hint", "message": "prefer pathlib.Path"},
    },
    {
        "title": "Type-annotate public APIs",
        "rationale": "Typed public symbols are the typing-docs standard; AI agents apply hints "
                     "inconsistently across a codebase. (AST-level property — prose principle.)",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Commit a lockfile; never install into the system interpreter",
        "rationale": "Reproducible builds need a committed uv.lock/poetry.lock; AI agents "
                     "routinely `pip install` ad hoc without updating project metadata.",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Don't duplicate code — extract and refactor",
        "rationale": "AI-assisted repos show 4-8x growth in cloned blocks and collapsed "
                     "refactoring rates (GitClear, 211M lines). Search for an existing helper "
                     "(recall/get_intent) before writing a new one.",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Fail fast — no speculative fallback paths",
        "rationale": "Defensive fallbacks that mask errors are a top LLM-agent antipattern; "
                     "raise early so failures surface at the root cause.",
        "ai_prone": True,
        "rule": None,
    },
]

# Scope note: "*.[jt]s" covers .js/.ts; .jsx/.tsx are deliberately not globbed
# ("*.[jt]s*" would also match .json) — pass them explicitly when relevant.
_JAVASCRIPT = [
    {
        "title": "No empty catch — every catch logs, rethrows, or handles",
        "rationale": "A silent `catch {}` hides failures (eslint:recommended no-empty); error "
                     "swallowing is a recurring theme in AI-mistake analyses. The regex catches "
                     "the single-line form; the principle binds for multi-line too.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"catch\s*(\([^)]*\))?\s*\{\s*\}",
                 "scope": "*.[jt]s", "severity": "error", "message": "empty catch — log, rethrow, or handle"},
    },
    {
        "title": "No eval / new Function / string-arg setTimeout",
        "rationale": "Arbitrary code-execution sinks, universally banned (Airbnb, Google, OWASP).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern",
                 "target": r"(^|[^.\w])eval\s*\(|new\s+Function\s*\(|set(Timeout|Interval)\(\s*[\"'`]",
                 "scope": "*.[jt]s", "severity": "error", "message": "code-execution sink"},
    },
    {
        "title": "No dynamic HTML sinks (innerHTML & friends)",
        "rationale": "Canonical DOM-XSS sinks; Veracode 2025 found AI code failed XSS defenses in "
                     "86% of relevant samples. Use textContent/safe APIs or a sanitizer.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"\.(innerHTML|outerHTML)\s*=|\.insertAdjacentHTML\(|document\.write(ln)?\(|dangerouslySetInnerHTML",
                 "scope": "*.[jt]s", "severity": "error", "message": "DOM-XSS sink — use textContent or a sanitizer"},
    },
    {
        "title": "const/let over var",
        "rationale": "`var` is function-scoped and hoisted — shadowing/closure bugs (ESLint no-var; Airbnb).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"(^|[\s;({])var\s+\w",
                 "scope": "*.[jt]s", "severity": "error", "message": "use const/let, not var"},
    },
    {
        "title": "=== over ==, with the `== null` carve-out",
        "rationale": "Loose equality coerces unpredictably; `x == null` is the one idiomatic "
                     "exception (ESLint eqeqeq 'smart').",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"[^=!<>]==(?!=)(?!\s*null\b)",
                 "scope": "*.[jt]s", "severity": "warning", "message": "use === (or `== null` for null/undefined)"},
    },
    {
        "title": "No console.log/debug in library code",
        "rationale": "Leftover debug output is one of the best-documented agent drift behaviors; "
                     "use a real logger (console.warn/error exempt).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"console\.(log|debug)\(",
                 "scope": "src/*.[jt]s", "severity": "warning", "message": "leftover console.log — use a logger"},
    },
    {
        "title": "ESM over CommonJS for new code",
        "rationale": "import/export is the standard; agents pattern-match older training data and "
                     "emit require(). Legacy CJS codebases and .cjs configs are fine — hint only.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"module\.exports|(^|[\s;(=])require\s*\(\s*[\"']",
                 "scope": "src/*.[jt]s", "severity": "hint", "message": "prefer ESM import/export"},
    },
]

_TYPESCRIPT = [
    {
        "title": "No @ts-ignore / @ts-nocheck",
        "rationale": "Suppresses errors silently forever; @ts-expect-error (with a description) "
                     "self-expires when the error is fixed (typescript-eslint ban-ts-comment, "
                     "in recommended). Suppression-to-make-it-compile is a documented agent pattern.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"@ts-(ignore|nocheck)\b",
                 "scope": "*.ts", "severity": "error", "message": "use @ts-expect-error with a description"},
    },
    {
        "title": "No `any` / `as any`",
        "rationale": "`any` disables type checking transitively; agents reach for it to silence "
                     "errors instead of fixing types (typescript-eslint no-explicit-any, in recommended).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"(:\s*|as\s+|<)any\b",
                 "scope": "*.ts", "severity": "warning", "message": "type it properly — `any` defeats TypeScript"},
    },
    {
        "title": "Keep tsconfig strict",
        "rationale": "`\"strict\": true` is the official baseline for new projects; agents loosen "
                     "flags as a quick fix. (Checked when tsconfig files are passed to guard.)",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"\"strict(NullChecks)?\"\s*:\s*false",
                 "scope": "tsconfig*.json", "severity": "error", "message": "don't loosen tsconfig strictness"},
    },
    {
        "title": "Prefer union types / as-const objects over enum",
        "rationale": "Enums emit runtime JS and numeric enums aren't type-safe; TS 5.8's "
                     "erasableSyntaxOnly signals the direction. Weakest-consensus item — hint.",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"(^|\s)(export\s+)?(const\s+)?enum\s+\w",
                 "scope": "*.ts", "severity": "hint", "message": "consider a union type / as-const object"},
    },
    {
        "title": "No floating promises — await, return, or void explicitly",
        "rationale": "An unawaited promise loses errors and breaks sequencing; needs type info to "
                     "check mechanically — enable typescript-eslint's no-floating-promises "
                     "(recommended-type-checked).",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Avoid non-null assertions (x!)",
        "rationale": "`!` silences the compiler with zero runtime check — a common agent shortcut "
                     "to silence strictNullChecks; use a real runtime check.",
        "ai_prone": True,
        "rule": None,
    },
]

_GO = [
    {
        "title": "Never discard errors with `_ =`",
        "rationale": "Blank-identifier discards make failure paths invisible (errcheck — a "
                     "golangci-lint default). Compile-time `var _ Iface` assertions don't match.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"^\s*_\s*(,\s*_\s*)*=[^=]",
                 "scope": "*.go", "severity": "warning", "message": "discarded error — handle or document why"},
    },
    {
        "title": "No panic in library/production paths",
        "rationale": "Uber Go style: panics are a major source of cascading failures — return an "
                     "error and let the caller decide (Must* init helpers are the exception).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"\bpanic\(",
                 "scope": "*.go", "severity": "warning", "message": "return an error instead of panicking"},
    },
    {
        "title": "Don't mint fresh contexts mid-stack",
        "rationale": "context.Background()/TODO() deep in a call chain severs cancellation and "
                     "tracing; ctx flows down as the first parameter (Go wiki; staticcheck).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"context\.(TODO|Background)\(\)",
                 "scope": "*.go", "severity": "hint", "message": "propagate ctx; Background() belongs at entry points"},
    },
    {
        "title": "Wrap errors with %w, not %v",
        "rationale": "fmt.Errorf(\"...: %v\", err) destroys the chain for errors.Is/As.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"fmt\.Errorf\([^)]*%v[^)]*\berr\b",
                 "scope": "*.go", "severity": "warning", "message": "wrap with %w to keep the error chain"},
    },
    {
        "title": "gofmt-clean; ctx first param; explicit returns in non-trivial functions",
        "rationale": "Universal Go review culture (Go Code Review Comments); enforce mechanically "
                     "with gofmt -l and the nakedret linter rather than regex.",
        "ai_prone": False,
        "rule": None,
    },
]

_RUST = [
    {
        "title": "No todo!() / unimplemented!() in finished work",
        "rationale": "Stub macros left in 'completed' code are a classic AI-agent failure mode — "
                     "they compile and then panic at runtime.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"\b(todo|unimplemented)!\s*\(",
                 "scope": "*.rs", "severity": "error", "message": "unfinished stub — implement or track in an issue"},
    },
    {
        "title": "No unwrap()/expect() in production code",
        "rationale": "Every unwrap is a latent panic site; prefer `?`, combinators, or match "
                     "(clippy unwrap_used/expect_used; tests are excluded by the src/ scope).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"\.unwrap\(\)|\.expect\(\"",
                 "scope": "src/*.rs", "severity": "warning", "message": "handle the Result/Option — unwrap panics"},
    },
    {
        "title": "panic!/unreachable! only for true invariants",
        "rationale": "Sometimes legitimate (exhaustive matches), often an error-handling dodge.",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"\b(panic|unreachable)!\s*\(",
                 "scope": "src/*.rs", "severity": "hint", "message": "is this a real invariant, or missing error handling?"},
    },
    {
        "title": "Every unsafe block carries a SAFETY: comment",
        "rationale": "Rust std-dev policy and Microsoft's guidelines: unsafe must be small, "
                     "wrapped safely, and justified (clippy undocumented_unsafe_blocks).",
        "ai_prone": False,
        "rule": {"kind": "forbid_pattern", "target": r"\bunsafe\s*(\{|fn|impl|trait)",
                 "scope": "src/*.rs", "severity": "hint", "message": "justify with a // SAFETY: comment (flag, not ban)"},
    },
    {
        "title": "clippy correctness is build-breaking; thiserror for libraries, anyhow for apps; don't clone reflexively",
        "rationale": "cargo clippy -- -D warnings in CI; typed errors for callers, aggregated "
                     "errors for apps; over-cloning is the canonical borrow-checker dodge.",
        "ai_prone": True,
        "rule": None,
    },
]

_AGENT = [
    {
        "title": "No private keys or provider credentials in the repo",
        "rationale": "Highest-blast-radius single-line mistake; AI-era repos leak measurably more "
                     "secrets (GitGuardian). Patterns from the gitleaks default ruleset.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b|ghp_[A-Za-z0-9]{36}",
                 "scope": "*", "severity": "error", "message": "credential material — remove and rotate it"},
    },
    {
        "title": "No hardcoded secret assignments",
        "rationale": "Generic api_key/token/password string literals; placeholders in tests will "
                     "need baselining once.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"(?i)\b(api[_-]?key|secret|token|passw(or)?d)\b\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{12,}[\"']",
                 "scope": "*", "severity": "warning", "message": "possible hardcoded secret — load from the environment"},
    },
    {
        "title": "Delete commented-out code — git is the safety net",
        "rationale": "Agents leave the old implementation behind comments 'just in case'; dead "
                     "code misleads the next reader (and the next agent).",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern",
                 "target": r"^\s*(//|#)\s*(if |for |while |return |def |func |fn |class |import |from |console\.log|print\()",
                 "scope": "*", "severity": "hint", "message": "commented-out code — delete it (git remembers)"},
    },
    {
        "title": "TODOs carry an owner or issue: TODO(name, #123)",
        "rationale": "Untracked agent TODOs accumulate fast; the tagged format is the "
                     "Google-style convention validated by the TOSEM TODO-quality study.",
        "ai_prone": True,
        "rule": {"kind": "forbid_pattern", "target": r"\b(TODO|FIXME|HACK|XXX)\b(?!\()",
                 "scope": "*", "severity": "hint", "message": "tag it: TODO(owner, #issue): …"},
    },
    {
        "title": "Tests accompany changes — and the agent runs them",
        "rationale": "The single most consistent vendor guidance (Anthropic, OpenAI, GitHub): "
                     "give the agent a check it can run, and require it to run it.",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Pin dependencies; commit lockfiles; never install ad hoc",
        "rationale": "Lockfile + review constrains supply-chain drift and agent-invented "
                     "packages/versions (OpenSSF; OWASP). Pair with `torsor deps`.",
        "ai_prone": True,
        "rule": None,
    },
    {
        "title": "Conventional Commits for agent-authored commits",
        "rationale": "Machine-checkable commit hygiene (feat/fix/docs/…): enables changelog and "
                     "semver automation.",
        "ai_prone": False,
        "rule": None,
    },
    {
        "title": "Small, focused functions; document public APIs",
        "rationale": "Concrete thresholds ('≤20 lines', 'doc every exported symbol') beat vague "
                     "'write clean code' — and long functions degrade the agent's own edits.",
        "ai_prone": False,
        "rule": None,
    },
]

PACKS: dict[str, dict] = {
    "python": {"label": "Python", "extensions": (".py", ".pyi"), "practices": _PYTHON},
    "javascript": {"label": "JavaScript", "extensions": (".js", ".jsx", ".mjs"), "practices": _JAVASCRIPT},
    "typescript": {"label": "TypeScript", "extensions": (".ts", ".tsx"),
                   "practices": _JAVASCRIPT + _TYPESCRIPT},
    "go": {"label": "Go", "extensions": (".go",), "practices": _GO},
    "rust": {"label": "Rust", "extensions": (".rs",), "practices": _RUST},
    "agent": {"label": "AI-agent hygiene (language-agnostic)", "extensions": (), "practices": _AGENT},
}


def available_languages() -> list[str]:
    return sorted(PACKS)


def detect_languages(root) -> list[str]:
    """Languages present in the repo (by source-file extension count, ignoring
    vendored/dot dirs), restricted to languages we ship a pack for."""
    root = Path(root)
    counts: Counter[str] = Counter()
    ext_to_lang = {ext: lang for lang, p in PACKS.items() for ext in p["extensions"]}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).parts
        if any(part in DEFAULT_IGNORE or part.startswith(".") for part in rel[:-1]):
            continue
        lang = ext_to_lang.get(path.suffix)
        if lang:
            counts[lang] += 1
    return [lang for lang, _ in counts.most_common()]


def pack(language: str) -> dict:
    if language not in PACKS:
        raise KeyError(language)
    return PACKS[language]


def render(language: str) -> str:
    """Human/agent-readable listing of one pack."""
    p = pack(language)
    lines = [f"## {p['label']} best practices ({len(p['practices'])})", ""]
    for item in p["practices"]:
        enforced = "guard-enforced" if item["rule"] else "principle"
        flag = " · AI-prone" if item["ai_prone"] else ""
        lines.append(f"- **{item['title']}** [{enforced}{flag}]")
        lines.append(f"  {item['rationale']}")
    lines.append("")
    lines.append(f"Adopt with: `torsor practices {language} --apply` (records an ADR; "
                 f"then `torsor guard --update-baseline` to grandfather existing code).")
    return "\n".join(lines)


def adr_payload(language: str) -> dict:
    """The record_decision() payload for adopting a pack."""
    p = pack(language)
    enforced = [item for item in p["practices"] if item["rule"]]
    prose = [item for item in p["practices"] if not item["rule"]]
    decision_lines = [f"- {item['title']}: {item['rationale']}" for item in p["practices"]]
    context = (
        f"Adopt the curated {p['label']} best-practice pack (consensus of major style guides "
        f"and default linter rules, weighted toward documented AI-coding failure modes)."
    )
    consequences = (
        f"{len(enforced)} practices carry machine-readable rules `torsor guard` enforces; "
        f"{len(prose)} are prose principles surfaced by `torsor rules`. Run "
        f"`torsor guard --update-baseline` once to grandfather pre-existing violations."
    )
    return {
        "title": f"Adopt {p['label']} best practices",
        "context": context,
        "decision": "\n".join(decision_lines),
        "consequences": consequences,
        "rules": [dict(item["rule"]) for item in enforced],
    }
