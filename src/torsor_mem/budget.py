from __future__ import annotations

_MARKER = "…[truncated]"


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
    return text[:max_chars].rstrip() + _MARKER
