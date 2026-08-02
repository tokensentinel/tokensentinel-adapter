"""Map engine LeakEvents to host-agnostic Decisions."""

from __future__ import annotations

from token_sentinel import LeakEvent

from token_sentinel_adapter.normalize import parse_stream_session_id
from token_sentinel_adapter.types import (
    Decision,
    DecisionAction,
    RuntimeStatus,
    WasteHit,
)


def leak_to_hit(event: LeakEvent) -> WasteHit:
    host_session_id, parsed_agent = parse_stream_session_id(event.session_id)
    # Prefer typed LeakEvent.agent_id (D12) when set; else composite session_id.
    agent_id = (getattr(event, "agent_id", None) or parsed_agent or "main")
    evidence_keys = tuple(sorted(event.evidence.keys())) if event.evidence else ()
    return WasteHit(
        type=event.type,
        rule=event.rule,
        confidence=event.confidence,
        estimated_burn=float(event.estimated_burn or 0.0),
        agent_id=agent_id,
        host_session_id=host_session_id,
        suggested_action=event.suggested_action or "",
        evidence_keys=evidence_keys,
    )


def format_reason(hits: list[WasteHit], *, mode: str) -> str:
    if not hits:
        return ""
    top = max(hits, key=lambda h: h.confidence)
    agent_bit = f" · agent: {top.agent_id}" if top.agent_id != "main" else ""
    burn_bit = ""
    if top.show_burn():
        burn_bit = f" · est. burn ≈ ${top.estimated_burn:.4f}"
    return (
        f"TokenSentinel · {top.type}{agent_bit} "
        f"(conf {top.confidence:.2f}){burn_bit}. "
        f"Mode: {mode}."
    )


def decision_from_events(
    events: list[LeakEvent],
    *,
    mode: str,
    status: RuntimeStatus,
    host_session_id: str,
    agent_id: str,
    block_on_waste: bool,
) -> Decision:
    hits = [leak_to_hit(e) for e in events]
    if not hits:
        return Decision(
            action=DecisionAction.ALLOW,
            reason="",
            status=status,
            hits=[],
            agent_id=agent_id,
            host_session_id=host_session_id,
        )

    reason = format_reason(hits, mode=mode)
    if block_on_waste and mode == "block":
        action = DecisionAction.DENY
    else:
        action = DecisionAction.ANNOTATE

    return Decision(
        action=action,
        reason=reason,
        status=status,
        hits=hits,
        agent_id=agent_id,
        host_session_id=host_session_id,
    )
