"""Time the hot paths on a corpus big enough to expose their scaling.

    uv run --extra dev python tests/bench/bench.py

Prints one line per path. Compare two runs across a change; the corpus is
deterministic, so the numbers are comparable on the same machine.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import build  # noqa: E402

from torsor_helper import db, operations as ops  # noqa: E402
from torsor_helper.config import TorsorConfig  # noqa: E402


def timed(label, fn, repeat=6):
    """Report min AND spread. Some of these paths swing 4x run to run on the
    same code and the same corpus (find and impact both walk the filesystem),
    so a single number reads as precision that is not there — and a change
    inside the spread proves nothing either way."""
    fn()  # warm
    times = sorted(_once(fn) for _ in range(repeat))
    lo, hi = times[0] * 1000, times[-1] * 1000
    flag = "   <- noisy, do not compare" if hi > lo * 1.5 else ""
    print(f"{label:<40} {lo:8.1f} ms  (max {hi:7.1f}){flag}")
    return lo


def _once(fn):
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def main():
    root = Path(tempfile.mkdtemp(prefix="torsor-bench-"))
    try:
        print(f"building corpus in {root} …")
        store = build(root)
        config = TorsorConfig()

        t = time.perf_counter()
        ops.map_repo(store, config)
        print(f"{'map_repo (cold)':<44} {(time.perf_counter() - t) * 1000:8.1f} ms")
        t = time.perf_counter()
        ops.map_repo(store, config)
        print(f"{'map_repo (unchanged repo)':<44} {(time.perf_counter() - t) * 1000:8.1f} ms")

        t = time.perf_counter()
        ops.recall(store, config, "term1 term2", limit=8)
        print(f"{'recall (cold, builds the index)':<44} {(time.perf_counter() - t) * 1000:8.1f} ms")

        timed("recall (warm, 8 hits)", lambda: ops.recall(store, config, "term3 term4", limit=8))
        timed("recall (filtered by type)",
              lambda: ops.recall(store, config, "term5", limit=8))
        timed("get_intent", lambda: ops.get_intent(store, config))
        timed("impact (hub symbol)", lambda: ops.impact(store, config, "fn0_0"))
        timed("connect", lambda: ops.connect(store, config, "fn5_1", "fn0_0"))
        timed("find (fuzzy)", lambda: ops.find_targets(store, config, "fn12", limit=20))

        conn = db.connect(store.paths.index_db)
        try:
            n = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            sym = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
            edges = conn.execute("SELECT COUNT(*) FROM symbol_edges").fetchone()[0]
        finally:
            conn.close()
        size = store.paths.index_db.stat().st_size / 1e6
        print(f"\ncorpus: {n} notes, {sym} symbols, {edges} edges, index {size:.1f} MB")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
