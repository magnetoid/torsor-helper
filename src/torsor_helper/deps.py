from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
import warnings
from pathlib import Path

from torsor_helper.cartographer import DEFAULT_IGNORE

_JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

_NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto", "dgram",
    "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https", "inspector", "module",
    "net", "os", "path", "perf_hooks", "process", "punycode", "querystring", "readline", "repl", "stream",
    "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
    "worker_threads", "zlib", "test",
}

# Common distribution-name -> import-name mismatches, used ONLY for the
# declared-deps fallback (an installed venv is the accurate source). Keeps the
# slopsquatting check conservative — better a missed phantom than a false alarm.
_ALIASES = {
    "pyyaml": "yaml", "pillow": "PIL", "beautifulsoup4": "bs4", "scikit-learn": "sklearn",
    "opencv-python": "cv2", "python-dateutil": "dateutil", "pyjwt": "jwt", "tomli-w": "tomli_w",
    "typing-extensions": "typing_extensions", "msgpack-python": "msgpack", "python-dotenv": "dotenv",
    "google-cloud-storage": "google", "psycopg2-binary": "psycopg2", "mysqlclient": "MySQLdb",
}

_DIST_RE = re.compile(r"[A-Za-z0-9_.\-]+")


def stdlib_names() -> set[str]:
    return set(sys.stdlib_module_names)


def _norm(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def _site_packages_top_levels(site: Path) -> set[str]:
    out: set[str] = set()
    for info in list(site.glob("*.dist-info")) + list(site.glob("*.egg-info")):
        got = False
        tl = info / "top_level.txt"
        if tl.exists():
            for line in tl.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line:
                    out.add(line.split("/")[0].split(".")[0])
                    got = True
        # RECORD lists every installed path — the robust source for wheels with
        # no top_level.txt and for PEP 420 namespace packages (no __init__.py).
        rec = info / "RECORD"
        if rec.exists():
            for line in rec.read_text(encoding="utf-8", errors="ignore").splitlines():
                path = line.split(",")[0].strip()
                if not path or path.startswith(("/", "..")):
                    continue
                head = path.split("/")[0]
                if head.endswith((".dist-info", ".data", ".egg-info")):
                    continue
                mod = head[:-3] if head.endswith(".py") else head.split(".")[0]
                if mod:
                    out.add(mod)
                    got = True
        if not got:
            out.add(_norm(info.name.split("-")[0]))  # last resort: the dist name
    for p in site.iterdir():  # bare packages/modules without dist-info
        if p.is_dir() and (p / "__init__.py").exists():
            out.add(p.name)
        elif p.suffix == ".py":
            out.add(p.stem)
    return out


def installed_import_names(root: Path) -> set[str]:
    """Top-level import names actually installed in the project's own virtualenv
    — the accurate, offline ground truth for 'does this package exist here'."""
    root = Path(root)
    out: set[str] = set()
    for venv in (root / ".venv", root / "venv"):
        if not venv.is_dir():
            continue
        for site in venv.glob("lib/*/site-packages"):
            out |= _site_packages_top_levels(site)
        win = venv / "Lib" / "site-packages"  # Windows layout
        if win.is_dir():
            out |= _site_packages_top_levels(win)
    return out


def first_party_names(root: Path) -> set[str]:
    """Top-level packages/modules defined in the repo (root and src/ layouts)."""
    root = Path(root)
    out: set[str] = set()
    for base in (root, root / "src"):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.name in DEFAULT_IGNORE:
                continue
            if p.is_dir() and (p / "__init__.py").exists():
                out.add(p.name)
            elif p.suffix == ".py":
                out.add(p.stem)
    return out


def _dist_from_spec(spec: str) -> str:
    m = _DIST_RE.match(spec.strip())
    return m.group(0) if m else ""


def declared_import_names(root: Path) -> set[str]:
    """Best-effort import names from declared dependencies (pyproject + requirements),
    via dist-name normalization plus a small alias table. A fallback when no venv."""
    root = Path(root)
    specs: list[str] = []
    py = root / "pyproject.toml"
    if py.exists():
        try:
            data = tomllib.loads(py.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        proj = data.get("project", {}) or {}
        specs += proj.get("dependencies", []) or []
        for extra in (proj.get("optional-dependencies", {}) or {}).values():
            specs += extra or []
        # PEP 735 dependency groups (uv's default home for dev deps)
        for grp in (data.get("dependency-groups", {}) or {}).values():
            specs += [it for it in (grp or []) if isinstance(it, str)]
        poetry = (data.get("tool", {}) or {}).get("poetry", {}) or {}
        specs += list((poetry.get("dependencies", {}) or {}).keys())
        for grp in (poetry.get("group", {}) or {}).values():
            specs += list(((grp or {}).get("dependencies", {}) or {}).keys())
    for req in root.glob("requirements*.txt"):
        try:
            for line in req.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith(("#", "-")):
                    specs.append(line)
        except OSError:
            continue

    out: set[str] = set()
    for spec in specs:
        name = _dist_from_spec(spec)
        if name:
            out |= _dist_import_candidates(name)
    return out


def _dist_import_candidates(name: str) -> set[str]:
    """Import names a distribution *might* provide, without installing it.

    The accurate answer comes from an installed venv's RECORD; this is the
    fallback when there is none — a fresh clone, CI before `pip install`. The
    alias table alone missed the common shapes: `discord.py` -> discord,
    `firecrawl-py` -> firecrawl, `honcho-ai` -> honcho, `python-telegram-bot` ->
    telegram, `PyNaCl` -> nacl. So also try the name with a python-/py prefix
    removed, and its first segment. Deliberately generous: ADR 0006 prefers a
    missed phantom to a false alarm, and a hallucinated package that happens to
    share a first segment with a declared one is the rare case."""
    nl = name.lower()
    out = {_norm(name), nl}
    if nl in _ALIASES:
        out.add(_ALIASES[nl])
    stem = nl
    for prefix in ("python-", "py-"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
    if stem.startswith("py") and len(stem) > 4 and stem[2] not in "-_.":
        out.add(_norm(stem[2:]))          # pynacl -> nacl, pyjwt -> jwt
    first = re.split(r"[-._]", stem)[0]
    if first:
        out.add(first)                    # discord.py, firecrawl-py, telegram-bot
    out.add(_norm(stem))
    return out


def _declared_in(directory: Path) -> set[str]:
    """Import names declared by one directory's pyproject.toml and
    requirements*.txt — the per-directory form of declared_import_names."""
    return declared_import_names(directory)


# An except clause naming any of these catches a failed import.
_IMPORT_GUARDS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def _catches_import_error(node) -> bool:
    for handler in node.handlers:
        if handler.type is None:
            return True
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        for t in types:
            name = t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else ""
            if name in _IMPORT_GUARDS:
                return True
    return False


def _import_statements(stmts, guarded: bool = False):
    """Yield (import node, guarded) for every import statement, in one pass.

    Statements only. An import cannot appear inside an expression, so this
    never descends into one — and expressions are most of any AST. The first
    version used ast.walk over the whole tree, then walked it again (and every
    try body once more) to find the guards: 18s on a real 2 400-file project
    became 280s. Nothing in the unit suite could see that; re-measuring on the
    real project did.

    `guarded` is true inside the BODY of a try whose handlers catch a failed
    import — the code itself declaring the package optional, which is the
    canonical optional-dependency idiom (torsor's own fastembed and tree_sitter
    imports use it) and not what a hallucinated import looks like. It was 57 of
    119 Python findings on that project. The handlers, `else` and `finally` are
    not guarded: a fallback import runs exactly when the first one failed."""
    for node in stmts:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node, guarded
            continue
        if isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
            yield from _import_statements(node.body, guarded or _catches_import_error(node))
            for handler in node.handlers:
                yield from _import_statements(handler.body, guarded)
            yield from _import_statements(node.orelse, guarded)
            yield from _import_statements(node.finalbody, guarded)
            continue
        for field in ("body", "orelse", "finalbody"):
            inner = getattr(node, field, None)
            if isinstance(inner, list):
                yield from _import_statements(inner, guarded)
        for case in getattr(node, "cases", None) or ():  # match statements
            yield from _import_statements(case.body, guarded)


# Candidate import names, found without parsing. An import statement starts a
# logical line or follows `;` or `:` (`try: import x`, `x = 1; import y`), so
# anchoring there over-approximates — a docstring line that says "import foo"
# matches too — and never under-approximates, which is the direction that
# matters: a false candidate costs one parse, a missed one would hide a finding.
_PY_IMPORT_LINE = re.compile(
    r"(?:^|[;:])[ \t]*(?:from[ \t]+(\.*)([A-Za-z_][\w.]*)?[ \t]+import\b|import[ \t]+([^\n;#]*))",
    re.M,
)


def _import_candidates(text: str) -> set[str] | None:
    """Top-level names every import in `text` could refer to, or None when the
    text is too irregular to pre-screen (a backslash continuation) and must be
    parsed."""
    out: set[str] = set()
    for dots, module, listed in _PY_IMPORT_LINE.findall(text):
        if listed:
            if "\\" in listed:
                return None
            for part in listed.split(","):
                name = part.strip().split(" ")[0].split(".")[0].strip("()")
                if name:
                    out.add(name)
        elif module and not dots:
            out.add(module.split(".")[0])
    return out


def _top_imports(text: str) -> list[tuple[str, int]]:
    try:
        with warnings.catch_warnings():
            # A project's own invalid escape sequences are its business, not a
            # line on this user's stderr with no filename attached.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[tuple[str, int]] = []
    for node, guarded in _import_statements(tree.body):
        if guarded:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name.split(".")[0], node.lineno))
        elif node.level and node.level > 0:  # relative import — first-party by definition
            continue
        elif node.module:
            out.append((node.module.split(".")[0], node.lineno))
    return out


def _js_package(spec: str) -> str | None:
    """Bare specifier → package name ('lodash/fp' → 'lodash', '@s/p/x' → '@s/p');
    None for relative/absolute paths, node: builtins, and '#'-prefixed subpath
    imports (package.json "imports" field — internal, not a dependency)."""
    if spec.startswith((".", "/", "node:", "#")):
        return None
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]


# ---- manifests: every package.json / tsconfig / go.mod, found once per call ----
#
# A repo is not one package. The first version read only the ROOT package.json,
# ROOT node_modules and ROOT go.mod, so in a monorepo every dependency a nested
# app declares was "unknown" — and so was every tsconfig path alias and every
# sibling workspace package. On a real JS/TS + Python monorepo that was 1 764
# false alarms out of 1 966, from a check ADR 0006 says must prefer a missed
# phantom over a false alarm. The model below is Node's own: a file sees the
# manifests of every directory between it and the root.


def _read_manifest(path: Path) -> dict:
    """A package.json or tsconfig, parsed; {} when it cannot be. Never raises."""
    try:
        data = _loads_jsonc(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _loads_jsonc(text: str):
    """json.loads for JSON-with-comments, which is what tsconfig actually is.

    String-aware: stripping `//` naively cuts "https://json.schemastore.org"
    in half, and every tsconfig that declares a $schema starts with one. Removes
    // and /* */ comments and trailing commas outside strings, nothing else."""
    out: list[str] = []
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        elif c == ",":
            k = _skip_blank(text, i + 1)
            if k < n and text[k] in "}]":
                i += 1  # a trailing comma: drop it
                continue
        out.append(c)
        i += 1
    return json.loads("".join(out))


def _skip_blank(text: str, k: int) -> int:
    """Index of the next character that is neither whitespace nor inside a
    comment. A trailing comma is often followed by a comment before the closing
    brace (`"b": 2, // last`), so skipping whitespace alone kept the comma."""
    n = len(text)
    while k < n:
        if text[k] in " \t\r\n":
            k += 1
        elif text.startswith("//", k):
            j = text.find("\n", k)
            k = n if j == -1 else j
        elif text.startswith("/*", k):
            j = text.find("*/", k + 2)
            k = n if j == -1 else j + 2
        else:
            break
    return k


class _ManifestIndex:
    """Every manifest in the repo, read once per `unknown_imports` call.

    Directories are root-relative POSIX strings, "" for the root itself."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.js_deps: dict[str, set[str]] = {}
        self.js_local: set[str] = set()          # every package.json "name" — workspaces
        self.alias_exact: set[str] = set()       # tsconfig paths key without a wildcard
        self.alias_prefixes: set[str] = set()    # "x/*" -> "x/"
        self.alias_roots: list[Path] = []        # "*" and bare baseUrl: resolve on disk
        self.go_prefixes: dict[str, list[str]] = {}
        self.go_local: set[str] = set()          # every go.mod module path
        self.py_declared: dict[str, set[str]] = {}  # dirs with a pyproject/requirements
        self.py_modules: dict[str, set[str]] = {}   # dir -> importable module/package names in it
        self._node_modules: dict[str, set[str]] = {}
        self._known_cache: dict[str, set[str]] = {}

    def js_known(self, relpath: str) -> set[str]:
        """Package names a file at `relpath` can import: builtins, every
        workspace package, and what each ancestor directory declares or has
        installed — Node resolves by walking up through node_modules, so a
        hoisted root dependency is visible to a nested app.

        By ancestry, not a union of every manifest in the repo: `react`
        declared by one app is not declared for a tool that lives beside it."""
        parent = relpath.rsplit("/", 1)[0] if "/" in relpath else ""
        if parent in self._known_cache:
            return self._known_cache[parent]
        known = set(_NODE_BUILTINS) | self.js_local
        for d in _ancestors(parent):
            known |= self.js_deps.get(d, set())
            known |= self._installed(d)
        # `import type { E } from 'hast'` resolves through @types/hast, and a
        # scoped package's types are @types/scope__name.
        known |= {_types_target(n) for n in known if n.startswith("@types/")}
        self._known_cache[parent] = known
        return known

    def _installed(self, d: str) -> set[str]:
        if d not in self._node_modules:
            self._node_modules[d] = _node_modules_names(self.root / d / "node_modules")
        return self._node_modules[d]

    def is_alias(self, spec: str) -> bool:
        # npm scopes cannot be empty, so `@/x` is a path alias by definition;
        # `~/` is the other near-universal one. Neither needs a config to know.
        if spec.startswith(("@/", "~/")):
            return True
        if spec in self.alias_exact or any(spec.startswith(p) for p in self.alias_prefixes):
            return True
        # A catch-all (`"*": ["src/*"]`, or a bare baseUrl) makes ANY bare
        # specifier possibly local. As a wildcard it would switch the check off
        # for the whole project; ignored, it would flag every local import. So
        # resolve it: local only if the target actually exists.
        head = spec.split("/", 1)[0]
        for base in self.alias_roots:
            candidate = base / head
            if candidate.exists() or any(candidate.with_suffix(ext).exists() for ext in _JS_SUFFIXES):
                return True
        return False

    def py_known(self, relpath: str) -> set[str]:
        """What a Python file can import beyond stdlib/venv/root: the modules
        beside it and beside every ancestor, plus what each ancestor declares.

        Python puts a script's own directory on sys.path, and plugin loaders
        and test runners put an ancestor there, so `from _common import x` with
        scripts/_common.py right beside the importer is first-party by the
        language's own definition. By ancestry, not "exists anywhere in the
        repo" — a helper.py in a sibling subtree is not importable from here."""
        parent = relpath.rsplit("/", 1)[0] if "/" in relpath else ""
        key = "py:" + parent
        if key in self._known_cache:
            return self._known_cache[key]
        known: set[str] = set()
        for d in _ancestors(parent):
            known |= self.py_modules.get(d, set())
            known |= self.py_declared.get(d, set())
        self._known_cache[key] = known
        return known

    def go_known(self, relpath: str) -> list[str]:
        parent = relpath.rsplit("/", 1)[0] if "/" in relpath else ""
        own: list[str] = []
        for d in _ancestors(parent):  # the nearest go.mod governs; take the deepest
            if d in self.go_prefixes:
                own = self.go_prefixes[d]
        return own + sorted(self.go_local)


def _types_target(name: str) -> str:
    bare = name[len("@types/"):]
    return "@" + bare.replace("__", "/", 1) if "__" in bare else bare


def _ancestors(parent: str) -> list[str]:
    """"" and every directory prefix of `parent`, shallowest first."""
    parts = [p for p in parent.split("/") if p]
    return [""] + ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _node_modules_names(nm: Path) -> set[str]:
    names: set[str] = set()
    try:
        if not nm.is_dir():
            return names
        for entry in nm.iterdir():
            try:
                if entry.name.startswith("@") and entry.is_dir():
                    names.update(f"{entry.name}/{sub.name}" for sub in entry.iterdir() if sub.is_dir())
                elif entry.is_dir():
                    names.add(entry.name)
            except OSError:
                continue  # unreadable entry — best-effort, keep what we have
    except OSError:
        pass  # unreadable node_modules — fall back to the manifests
    return names


def _manifest_index(root: Path) -> _ManifestIndex:
    """One walk over the repo for every package.json, tsconfig*.json and go.mod.

    Prunes the same directories the map does — node_modules above all, which in
    a real project holds thousands of package.json files, none of them ours.
    tsconfig aliases are collected repo-wide rather than per nearest config:
    `extends` chains make "nearest" wrong anyway, and the union errs in the
    direction ADR 0006 asks for."""
    import os

    root = Path(root)
    index = _ManifestIndex(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in DEFAULT_IGNORE)
        here = Path(dirpath)
        rel = here.relative_to(root).as_posix()
        rel = "" if rel == "." else rel
        # Importable names in this directory, collected during the walk rather
        # than by statting each ancestor per file: its .py stems, and — once we
        # see a package's __init__.py — that package's name in its parent.
        index.py_modules.setdefault(rel, set()).update(n[:-3] for n in filenames if n.endswith(".py"))
        if rel and "__init__.py" in filenames:
            parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
            index.py_modules.setdefault(parent, set()).add(rel.rsplit("/", 1)[-1])
        if "pyproject.toml" in filenames or any(
            n.startswith("requirements") and n.endswith(".txt") for n in filenames
        ):
            index.py_declared[rel] = _declared_in(here)
        for name in filenames:
            if name == "package.json":
                data = _read_manifest(here / name)
                declared: set[str] = set()
                for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    section = data.get(key)
                    if isinstance(section, dict):
                        declared.update(section)
                index.js_deps[rel] = declared
                if isinstance(data.get("name"), str):
                    index.js_local.add(data["name"])
            elif name.startswith("tsconfig") and name.endswith(".json"):
                _collect_aliases(index, here, _read_manifest(here / name))
            elif name == "go.mod":
                prefixes = _go_mod_prefixes(here / name)
                index.go_prefixes[rel] = prefixes
                module = _go_module_path(here / name)
                if module:
                    index.go_local.add(module)
    return index


def _collect_aliases(index: _ManifestIndex, config_dir: Path, data: dict) -> None:
    options = data.get("compilerOptions")
    if not isinstance(options, dict):
        return
    base_url = options.get("baseUrl")
    base = (config_dir / base_url) if isinstance(base_url, str) else config_dir
    paths = options.get("paths")
    if isinstance(paths, dict):
        for key, targets in paths.items():
            if not isinstance(key, str):
                continue
            if key == "*":
                for target in targets if isinstance(targets, list) else []:
                    if isinstance(target, str) and target.endswith("*"):
                        index.alias_roots.append(base / target[:-1])
            elif key.endswith("*"):
                index.alias_prefixes.add(key[:-1])
            else:
                index.alias_exact.add(key)
    elif isinstance(base_url, str):
        # A baseUrl with no `paths` makes bare imports resolve under it — the
        # older Create-React-App style. Same treatment as a "*" catch-all.
        index.alias_roots.append(base)


def _unknown_js_imports(root: Path, relpath: str, text: str, index: _ManifestIndex) -> list[dict]:
    from torsor_helper import languages

    known = index.js_known(relpath)
    out = []
    for spec, line in languages.import_specifiers(relpath, text):
        name = _js_package(spec)
        if name and name not in known and not index.is_alias(spec):
            out.append({"file": relpath, "line": line, "name": name})
    return out


_GO_REQUIRE = re.compile(r"^\s*(?:require\s+)?([A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)+)\s+v", re.M)
_GO_REPLACE = re.compile(r"^\s*(?:replace\s+)?([A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)+)\s*=>", re.M)
_GO_MODULE = re.compile(r"^module\s+(\S+)", re.M)


def _go_mod_prefixes(mod: Path) -> list[str]:
    try:
        text = mod.read_text(encoding="utf-8")
    except OSError:
        return []
    prefixes = _GO_REQUIRE.findall(text)
    prefixes += _GO_REPLACE.findall(text)  # a replace directive's left side is still imported
    m = _GO_MODULE.search(text)
    if m:
        prefixes.append(m.group(1))
    return prefixes


def _go_module_path(mod: Path) -> str:
    try:
        m = _GO_MODULE.search(mod.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return m.group(1) if m else ""


def _unknown_go_imports(root: Path, relpath: str, text: str, index: _ManifestIndex) -> list[dict]:
    from torsor_helper import languages

    prefixes = index.go_known(relpath)
    out = []
    for spec, line in languages.import_specifiers(relpath, text):
        if "." not in spec.split("/", 1)[0]:
            continue  # stdlib: first segment has no dot
        if any(spec == p or spec.startswith(p + "/") for p in prefixes):
            continue
        out.append({"file": relpath, "line": line, "name": spec})
    return out


def unknown_imports(root: Path, files) -> list[dict]:
    """Flag top-level absolute imports that resolve to NO known package — a
    possible hallucinated dependency (slopsquatting). Fully offline; conservative
    (union of stdlib + installed-venv + first-party + declared). Advisory: this
    checks only the top-level name, so a hallucinated *submodule* of a real
    package (e.g. `numpy.fake`) is not caught — verify suggestions independently."""
    root = Path(root)
    known = stdlib_names() | installed_import_names(root) | first_party_names(root) | declared_import_names(root)
    index: _ManifestIndex | None = None  # built at most once per call, lazily (~0.1s on 3k files)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for f in files:
        path = (root / f) if not Path(f).is_absolute() else Path(f)
        try:
            # utf-8-sig: a BOM would make ast.parse fail and the file silently pass
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.name

        suffix = path.suffix
        if index is None:
            index = _manifest_index(root)
        if suffix == ".go":
            found = _unknown_go_imports(root, rel, text, index)
        elif suffix in _JS_SUFFIXES:
            found = _unknown_js_imports(root, rel, text, index)
        else:
            local = index.py_known(rel)
            candidates = _import_candidates(text)
            if candidates is not None and all(c in known or c in local for c in candidates):
                # Every import names something known, so no finding is
                # possible — skip the parse, which is the whole cost: ~9 ms a
                # file, 21 of 28 seconds on a 2 400-file project.
                continue
            found = [
                {"file": rel, "line": lineno, "name": name}
                for name, lineno in _top_imports(text)
                if name and name not in known and name not in local
            ]

        for item in found:
            key = (item["file"], item["name"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out
