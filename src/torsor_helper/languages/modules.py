from __future__ import annotations

# Every suffix any registered language claims. Kept here (a leaf module) so
# norm_module can strip them without importing the registry — which would be
# circular, since the registry imports the extractors that call norm_module.
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go")


def strip_suffix(module: str) -> str:
    for suffix in SOURCE_SUFFIXES:
        if module.endswith(suffix):
            return module[: -len(suffix)]
    return module


def norm_module(module: str) -> str:
    """Normalize a module key to dotted form so a file relpath ("pkg/dates.py")
    and an import target ("pkg.dates") compare equal. Strips a leading source-root
    segment ("src/", "lib/") so a src-layout file canonicalizes to its import
    name. JS/TS `pkg/index.ts` collapses to `pkg` — the key `import './pkg'`
    resolves to. Not injective across duplicate path-tails (see ADR 0004)."""
    stripped = strip_suffix(module)
    if stripped.endswith("/index") and not module.endswith(".py"):
        stripped = stripped[: -len("/index")]
    dotted = stripped.replace("/", ".")
    for root in ("src.", "lib."):
        if dotted.startswith(root):
            return dotted[len(root):]
    return dotted
