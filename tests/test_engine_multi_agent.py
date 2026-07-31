"""Multi-agent isolation — sibling agents must not pool."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from token_sentinel_adapter import EngineHandle
from token_sentinel_adapter.types import AdapterEvent, DecisionAction


def _tool_event(
    *,
    host_session: str,
    agent_id: str,
    tool: str,
    tool_input: dict,
    ts: datetime,
) -> AdapterEvent:
    return AdapterEvent(
        host="claude-code",
        host_event="PostToolUse",
        host_session_id=host_session,
        agent_id=agent_id,
        tool_name=tool,
        tool_input=tool_input,
        timestamp=ts,
    )


def test_sibling_agents_do_not_trigger_shared_retry_storm() -> None:
    """Each sibling retries twice (identical tool) — must NOT storm as 4."""
    engine = EngineHandle(project="test", preset="observe")
    host = "host-session-A"
    base = datetime.now(timezone.utc)
    payload = {"command": "npm test -- --runInBand"}

    # Agent B: 2 identical calls
    for i in range(2):
        r = engine.handle(
            _tool_event(
                host_session=host,
                agent_id="worker-b",
                tool="Bash",
                tool_input=payload,
                ts=base + timedelta(seconds=i),
            )
        )
        assert r.decision.action in (DecisionAction.ALLOW, DecisionAction.ANNOTATE)

    # Agent C: 2 identical calls (same hash as B if pooled — would be 4 total)
    for i in range(2):
        r = engine.handle(
            _tool_event(
                host_session=host,
                agent_id="worker-c",
                tool="Bash",
                tool_input=payload,
                ts=base + timedelta(seconds=10 + i),
            )
        )
        types = {h.type for h in r.decision.hits}
        assert "retry_storm" not in types, "siblings must not pool into retry_storm"

    # Same agent alone reaching 5 identical → should storm
    for i in range(5):
        r = engine.handle(
            _tool_event(
                host_session=host,
                agent_id="worker-d",
                tool="Bash",
                tool_input=payload,
                ts=base + timedelta(seconds=20 + i),
            )
        )
    assert any(h.type == "retry_storm" for h in r.decision.hits)
    assert all(h.agent_id == "worker-d" for h in r.decision.hits if h.type == "retry_storm")


def test_tool_loop_fires_for_single_agent() -> None:
    engine = EngineHandle(project="test", preset="observe")
    host = "host-session-B"
    base = datetime.now(timezone.utc)
    # Near-identical Read args
    hits = []
    for i in range(4):
        r = engine.handle(
            AdapterEvent(
                host="claude-code",
                host_event="PostToolUse",
                host_session_id=host,
                agent_id="main",
                tool_name="Read",
                tool_input={"path": "src/app.py", "offset": 0},
                timestamp=base + timedelta(seconds=i),
            )
        )
        hits = r.decision.hits
    assert any(h.type == "tool_loop" for h in hits), hits


def test_strict_deny_when_allowed() -> None:
    engine = EngineHandle(project="test", preset="strict")
    host = "host-session-C"
    base = datetime.now(timezone.utc)
    payload = {"command": "true"}
    last = None
    for i in range(5):
        last = engine.handle(
            _tool_event(
                host_session=host,
                agent_id="main",
                tool="Bash",
                tool_input=payload,
                ts=base + timedelta(seconds=i),
            )
        )
    assert last is not None
    # After enough identical retries, block mode should deny
    assert last.decision.action == DecisionAction.DENY
    assert last.decision.hits
