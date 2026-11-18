"""The agent eval's stream parser: a run's record must say which tools and hooks
spent the time, or a cost difference between the arms cannot be explained."""
import importlib.util
import json
from pathlib import Path

_RUN = Path(__file__).parent / "bench" / "agent_eval" / "run.py"


def _run_module():
    spec = importlib.util.spec_from_file_location("agent_eval_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ev(t, **event):
    return (t, json.dumps(event) + "\n")


def test_parse_stream_keeps_the_result_and_times_tools_and_hooks():
    hook_out = json.dumps({"hookSpecificOutput": {"additionalContext": "x" * 42}})
    lines = [
        _ev(0.0, type="system", subtype="hook_started", hook_id="h1", hook_name="SessionStart:startup"),
        _ev(0.5, type="system", subtype="hook_response", hook_id="h1", hook_name="SessionStart:startup",
            outcome="success", stdout=hook_out),
        _ev(1.0, type="assistant", message={"content": [{"type": "tool_use", "id": "t1", "name": "ToolSearch"}]}),
        _ev(1.2, type="user", message={"content": [{"type": "tool_result", "tool_use_id": "t1"}]}),
        _ev(2.0, type="assistant", message={"content": [{"type": "tool_use", "id": "t2", "name": "Read"}]}),
        (2.1, "not json\n"),
        _ev(3.0, type="result", subtype="success", is_error=False, result="Done.", num_turns=3, total_cost_usd=0.01),
    ]

    data = _run_module().parse_stream(lines)

    assert data["result"] == "Done." and data["num_turns"] == 3
    assert data["trace"]["hooks"] == [
        {"hook": "SessionStart:startup", "ms": 500, "outcome": "success", "context_chars": 42}]
    assert data["trace"]["tools"] == [{"tool": "ToolSearch", "ms": 200}, {"tool": "Read", "ms": None}]


def test_parse_stream_without_a_result_is_an_error_with_the_tail():
    data = _run_module().parse_stream([(0.0, "Failed to authenticate\n")])

    assert data["is_error"] is True
    assert "Failed to authenticate" in data["result"]
    assert data["trace"] == {"tools": [], "hooks": []}
