from __future__ import annotations

from statistics import pstdev

from torsor_helper import db
from torsor_helper.cartographer import norm_module
from torsor_helper.models import Recommendation


def find_hubs(conn, *, min_fan_in: int = 8, sigma: float = 2.0):
    """'God nodes' in the symbol call graph: symbols an unusually large number of
    *distinct* callers depend on. A symbol qualifies when its fan-in clears both
    an absolute floor (`min_fan_in`) and a statistical-outlier bar (mean + `sigma`
    × stdev across all referenced symbols) — the outlier test keeps small or
    uniformly-connected repos quiet without the mean-vs-self trap of a flat ratio.
    Returns [(module, name, fan_in)] sorted strongest-first; [] without an index."""
    if conn is None:
        return []
    counts = db.symbol_fan_in(conn)
    if not counts:
        return []
    # Only first-party symbols are actionable — flagging stdlib/third-party hubs
    # (pathlib.Path, datetime) as "stabilize behind a seam" is noise.
    first_party = {norm_module(m) for m in db.modules(conn)}
    fanins = [fi for _m, _n, fi in counts]
    mean = sum(fanins) / len(fanins)
    floor = max(float(min_fan_in), mean + sigma * pstdev(fanins))
    hubs = [(nm, n, fi) for m, n, fi in counts
            if fi >= floor and (nm := norm_module(m)) in first_party]
    hubs.sort(key=lambda t: (-t[2], t[0], t[1]))
    return hubs


def find_hub_recs(conn, limit: int = 3, *, min_fan_in: int = 8) -> list[Recommendation]:
    """Surface the top God nodes as advisory recs — high fan-in concentrates
    architectural risk (a change here ripples widely; consider a seam/interface)."""
    out: list[Recommendation] = []
    for module, name, fan_in in find_hubs(conn, min_fan_in=min_fan_in)[:limit]:
        out.append(Recommendation(
            kind="hub", severity="suggest",
            message=(
                f"{module}::{name} is a hub — referenced by {fan_in} distinct callers. "
                f"Changes here ripple widely; consider stabilizing it behind a seam/interface."
            ),
            action=f"review {module}::{name}", source=module,
            key=f"hub:{module}:{name}", score=float(fan_in),
        ))
    return out
