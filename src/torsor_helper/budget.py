from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

_MARKER = "…[truncated]"

T = TypeVar("T")


def estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    if chars_per_token <= 0:
        chars_per_token = 4
    return len(text) // chars_per_token


def truncate_to_tokens(text: str, max_tokens: int, chars_per_token: int = 4) -> str:
    if chars_per_token <= 0:
        chars_per_token = 4
    max_chars = max(0, max_tokens) * chars_per_token
    if len(text) <= max_chars:
        return text
    # The marker is spent from the budget, not added on top of it: appending it
    # after the cut made every "budgeted" path overrun by the marker's length.
    if max_chars <= len(_MARKER):
        return text[:max_chars]
    return text[: max_chars - len(_MARKER)].rstrip() + _MARKER


# What a rendered recall hit costs beyond its title and snippet: the "### "
# heading, the " (TIER)" suffix, and the blank line before the next hit.
_HIT_FRAMING_TOKENS = 6


def hit_cost(title: str, snippet: str, chars_per_token: int = 4) -> int:
    """Token cost of one rendered recall hit — title and framing included.

    Billing only the snippet made every recall budget optimistic: both adapters
    render `### {title} ({tier})` above each snippet, so a wide recall overran
    its ceiling by roughly the sum of its titles (measured: 1859 rendered
    tokens against a 1500 budget). Over-billing slightly is the safe direction
    for a budget.
    """
    return (estimate_tokens(title, chars_per_token)
            + estimate_tokens(snippet, chars_per_token)
            + _HIT_FRAMING_TOKENS)


def cap_items(items: Sequence[T], max_items: int, *, more: str = "") -> tuple[list[T], str]:
    """Keep the first `max_items` and report what was left out.

    Returns `(kept, tail)`, where `tail` is "" when nothing was dropped and
    otherwise a single line naming the number hidden (plus `more`, a hint for
    getting the rest). The tail is the point: a *silent* truncation is more
    expensive than no truncation at all, because the agent then treats a partial
    list as the whole answer — or re-queries blindly. One honest line costs ~10
    tokens and removes both failure modes.

    A non-positive `max_items` means "no cap", so a caller can disable it
    without branching.
    """
    kept = list(items)
    if max_items <= 0 or len(kept) <= max_items:
        return kept, ""
    hidden = len(kept) - max_items
    hint = f" ({more})" if more else ""
    return kept[:max_items], f"… +{hidden} more{hint}"
