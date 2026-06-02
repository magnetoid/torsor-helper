from torsor_helper.snippets import best_snippet

BODY = (
    "Intro paragraph about general project setup and onboarding.\n\n"
    "Second paragraph discussing unrelated background material here.\n\n"
    "The retry policy uses exponential backoff with retry retry retry on failure.\n\n"
    "Closing notes and a short summary at the very end."
)


def test_picks_densest_section_not_first_hit():
    snip = best_snippet(BODY, ["retry", "backoff"], width=120)
    assert "backoff" in snip
    assert "retry retry" in snip  # the dense cluster, not the lone first occurrence
    assert "Intro paragraph" not in snip


def test_single_term_window():
    snip = best_snippet(BODY, ["closing"], width=80)
    assert "Closing notes" in snip


def test_no_match_returns_prefix():
    snip = best_snippet(BODY, ["zzzznotfound"], width=40)
    assert snip == BODY[:40].strip()


def test_empty_terms_returns_prefix():
    assert best_snippet(BODY, [], width=40) == BODY[:40].strip()


def test_heading_match_breaks_toward_heading_section():
    body = (
        "## Overview\nsome generic text mentioning auth once.\n\n"
        "## Auth retry\nthis section is about it.\n"
    )
    # both sections mention 'auth' once, but the second has it in the heading
    snip = best_snippet(body, ["auth"], width=120)
    assert "Auth retry" in snip


def test_deterministic():
    a = best_snippet(BODY, ["retry", "backoff"], width=120)
    b = best_snippet(BODY, ["retry", "backoff"], width=120)
    assert a == b
