from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
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
        if not name:
            continue
        nl = name.lower()
        out.add(_norm(name))
        out.add(nl)
        if nl in _ALIASES:
            out.add(_ALIASES[nl])
    return out


def _top_imports(text: str) -> list[tuple[str, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:  # relative import — first-party by definition
                continue
            if node.module:
                out.append((node.module.split(".")[0], node.lineno))
    return out


def _js_package(spec: str) -> str | None:
    """Bare specifier → package name ('lodash/fp' → 'lodash', '@s/p/x' → '@s/p');
    None for relative/absolute paths and node: builtins."""
    if spec.startswith((".", "/", "node:")):
        return None
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]


def _js_known(root: Path) -> set[str]:
    known = set(_NODE_BUILTINS)
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            known.update((data.get(key) or {}).keys())
    nm = root / "node_modules"
    if nm.is_dir():
        for entry in nm.iterdir():
            if entry.name.startswith("@") and entry.is_dir():
                known.update(f"{entry.name}/{sub.name}" for sub in entry.iterdir() if sub.is_dir())
            elif entry.is_dir():
                known.add(entry.name)
    return known


def _unknown_js_imports(root: Path, relpath: str, text: str) -> list[dict]:
    from torsor_helper import languages

    known = _js_known(root)
    out = []
    for spec, line in languages.import_specifiers(relpath, text):
        name = _js_package(spec)
        if name and name not in known:
            out.append({"file": relpath, "line": line, "name": name})
    return out


def unknown_imports(root: Path, files) -> list[dict]:
    """Flag top-level absolute imports that resolve to NO known package — a
    possible hallucinated dependency (slopsquatting). Fully offline; conservative
    (union of stdlib + installed-venv + first-party + declared). Advisory: this
    checks only the top-level name, so a hallucinated *submodule* of a real
    package (e.g. `numpy.fake`) is not caught — verify suggestions independently."""
    root = Path(root)
    known = stdlib_names() | installed_import_names(root) | first_party_names(root) | declared_import_names(root)
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
        if suffix in _JS_SUFFIXES:
            found = _unknown_js_imports(root, rel, text)
        elif suffix == ".go":
            # Task 10 wires up a Go-specific check; skip for now rather than
            # falling through to the Python ast parser (which would just fail
            # silently on Go syntax and add nothing).
            continue
        else:
            found = [
                {"file": rel, "line": lineno, "name": name}
                for name, lineno in _top_imports(text)
                if name and name not in known
            ]

        for item in found:
            key = (item["file"], item["name"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out
