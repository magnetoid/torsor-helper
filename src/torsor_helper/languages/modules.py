from __future__ import annotations

# Every suffix any registered language claims. Kept here (a leaf module) so
# norm_module can strip them without importing the registry — which would be
# circular, since the registry imports the extractors that call norm_module.
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go")


def strip_suffix(module: str) -> str:
    """`.py` comes off any key. A NON-Python suffix comes off only a path-shaped
    key (one containing "/"), because a dotted *module* name may legitimately end
    in a foreign suffix — `torsor_helper.languages.go`, `app.models.js` — and
    truncating it to `torsor_helper.languages` breaks reference resolution."""
    if module.endswith(".py"):
        return module[: -len(".py")]
    if "/" not in module:
        return module
    for suffix in SOURCE_SUFFIXES:
        if module.endswith(suffix):
            return module[: -len(suffix)]
    return module


def _canonicalize(stripped: str, original: str) -> str:
    """Shared tail of norm_module/norm_path: collapse a JS/TS `index` file to its
    directory, dot the separators, and drop a leading source root so a src-layout
    file canonicalizes to its import name."""
    if stripped.endswith("/index") and not original.endswith(".py"):
        stripped = stripped[: -len("/index")]
    dotted = stripped.replace("/", ".")
    for root in ("src.", "lib."):
        if dotted.startswith(root):
            return dotted[len(root):]
    return dotted


def norm_module(module: str) -> str:
    """Canonical key for a module reference that MAY be a dotted import target.

    Conservative by necessity: "pkg.go" is both a plausible Python import target
    (pkg/go.py) and a plausible root-level Go file, and no string rule separates
    them — so a non-Python suffix is kept unless the key is visibly a path. When
    you know you hold a file path, call `norm_path`, which has no such doubt."""
    return _canonicalize(strip_suffix(module), module)


def norm_path(relpath: str) -> str:
    """Canonical key for a FILE PATH — the caller knows it is one, so a
    registered suffix always comes off, `helper.ts` at the scan root included.

    Splitting this out is what makes a flat JS/TS repo work: the file's own key
    and the key its importers resolve to are derived by different code paths, and
    while `norm_module` had to keep "helper.ts" intact (it cannot tell that from
    a dotted name), the symbol side always knows better."""
    stripped = relpath
    for suffix in SOURCE_SUFFIXES:
        if relpath.endswith(suffix):
            stripped = relpath[: -len(suffix)]
            break
    return _canonicalize(stripped, relpath)
