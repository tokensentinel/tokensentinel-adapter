"""Report formatting and decision wire shape."""

from __future__ import annotations

from datetime import datetime, timezone

from token_sentinel.events import LeakEvent

from token_sentinel_adapter.decisions import decision_from_events, format_reason
from token_sentinel_adapter.report import format_session_report
from token_sentinel_adapter.types import RuntimeStatus, WasteHit


def test_decision_wire_omits_zero_burn() -> None:
    ev = LeakEvent(
        type="tool_loop",
        confidence=0.9,
        project="p",
        session_id="sess::main",
        rule="v0.tool_loop",
        evidence={"tool": "Read"},
        estimated_burn=0.0,
        suggested_action="pause",
        raised_at=datetime.now(timezone.utc),
    )
    d = decision_from_events(
        [ev],
        mode="log",
        status=RuntimeStatus.HEALTHY,
        host_session_id="sess",
        agent_id="main",
        block_on_waste=False,
    )
    wire = d.to_wire()
    assert wire["decision"] == "annotate"
    assert wire["events"][0]["estimated_burn"] is None


def test_format_reason_includes_agent_when_not_main() -> None:
    hits = [
        WasteHit(
            type="tool_loop",
            rule="v0.tool_loop",
            confidence=0.91,
            estimated_burn=0.0,
            agent_id="explore-2",
            host_session_id="s",
        )
    ]
    reason = format_reason(hits, mode="observe")
    assert "explore-2" in reason
    assert "tool_loop" in reason


def test_session_report() -> None:
    hits = [
        WasteHit(
            type="tool_loop",
            rule="v0.tool_loop",
            confidence=0.9,
            estimated_burn=0.0,
            agent_id="main",
            host_session_id="s1",
        ),
        WasteHit(
            type="tool_loop",
            rule="v0.tool_loop",
            confidence=0.9,
            estimated_burn=0.0,
            agent_id="explore-1",
            host_session_id="s1",
        ),
    ]
    text = format_session_report(
        host_session_id="s1",
        mode="observe",
        status=RuntimeStatus.HEALTHY,
        hits=hits,
        tool_call_count=10,
    )
    assert "tool_loop" in text
    assert "explore-1" in text
