from torsor_helper.budget import estimate_tokens, truncate_to_tokens


def test_estimate_tokens_uses_chars_per_token():
    assert estimate_tokens("a" * 40, chars_per_token=4) == 10
    assert estimate_tokens("", chars_per_token=4) == 0


def test_truncate_keeps_short_text():
    assert truncate_to_tokens("hello", max_tokens=100, chars_per_token=4) == "hello"


def test_truncate_cuts_long_text_and_marks_it():
    text = "x" * 400  # 100 tokens at cpt=4
    out = truncate_to_tokens(text, max_tokens=10, chars_per_token=4)
    assert out.endswith("…[truncated]")
    assert len(out) <= 40 + len("…[truncated]")
