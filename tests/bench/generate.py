"""Build a throwaway project big enough for the hot paths to hurt.

Not a fixture for the test suite — the suite must stay fast. This is for
`bench.py`, so a performance claim in a commit message has a number behind it.
"""
from __future__ import annotations

import random
from pathlib import Path

from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

WORDS = [f"term{i}" for i in range(800)]


def build(root: Path, *, notes: int = 5000, modules: int = 200, per_module: int = 20) -> Store:
    rng = random.Random(1234)  # deterministic: two runs measure the same corpus
    store = Store(TorsorPaths(root))
    store.scaffold()

    for i in range(notes):
        body = " ".join(rng.choice(WORDS) for _ in range(120))
        link = f"\n\nSee [[note-{rng.randrange(notes)}]].\n" if i % 5 == 0 else "\n"
        (store.paths.memory_dir / f"note-{i}.md").write_text(
            f"---\ntype: note\nstatus: active\n---\n\n# Note {i} about {rng.choice(WORDS)}\n\n{body}{link}",
            encoding="utf-8",
        )

    pkg = root / "pkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("")
    for m in range(modules):
        lines = ["from pkg.mod0 import fn0_0\n"] if m else []
        for f in range(per_module):
            lines.append(f"def fn{m}_{f}(x):\n    return fn0_0(x) if x else {f}\n")
        (pkg / f"mod{m}.py").write_text("".join(lines))
    return store


if __name__ == "__main__":
    import sys
    build(Path(sys.argv[1]))
    print("built")
