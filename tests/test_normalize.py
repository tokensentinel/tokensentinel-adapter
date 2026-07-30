"""Tests for CallRecord building and stream keys."""

from __future__ import annotations

from token_sentinel_adapter.normalize import (
    build_call_record,
    parse_stream_session_id,
    stream_session_id,
)
from token_sentinel_adapter.types import AdapterEvent


def test_stream_session_id_isolates_agents() -> None:
    a = stream_session_id("sess-1", "main")
    b = stream_session_id("sess-1", "explore-2")
    assert a != b
    assert parse_stream_session_id(a) == ("sess-1", "main")
    assert parse_stream_session_id(b) == ("sess-1", "explore-2")


def test_build_call_record_redacts_secrets() -> None:
    event = AdapterEvent(
        host="claude-code",
        host_event="PostToolUse",
        host_session_id="s1",
        agent_id="main",
        tool_name="Bash",
        tool_input={"command": "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"},
    )
    call = build_call_record(event)
    dumped = str(call.tool_calls)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in dumped
    assert call.session_id == "s1::main"
    assert call.raw_request["agent_id"] == "main"
    assert call.raw_request["host_session_id"] == "s1"


def test_build_call_record_estimates_large_tool_output() -> None:
    big = "x" * 8000  # ~2000 tokens at 4 chars/token
    event = AdapterEvent(
        host="claude-code",
        host_event="PostToolUse",
        host_session_id="s1",
        tool_name="Read",
        tool_input={"path": "huge.log"},
        tool_output=big,
    )
    call = build_call_record(event)
    assert call.prompt_tokens >= 500
