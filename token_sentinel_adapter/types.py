"""Host-agnostic types for the adapter kernel (architecture D9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


class RuntimeStatus(str, Enum):
    """Visible health of the evaluation path (architecture D11 / UX S3)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class DecisionAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ANNOTATE = "annotate"


@dataclass(frozen=True)
class WasteHit:
    """One rule fire, already scoped to an agent stream."""

    type: str
    rule: str
    confidence: float
    estimated_burn: float
    agent_id: str
    host_session_id: str
    suggested_action: str = ""
    evidence_keys: tuple[str, ...] = ()

    def show_burn(self) -> bool:
        """Whether UX may show a dollar figure (token-backed estimate)."""
        return self.estimated_burn > 0.0


@dataclass
class AdapterEvent:
    """Normalized host event. Host bridges only construct this type.

    Attributes follow architecture D9. Rule windows use
    ``(host_session_id, agent_id)`` via :func:`stream_session_id`.
    """

    host: str
    host_event: str
    host_session_id: str
    agent_id: str = "main"
    agent_type: str | None = None
    parent_session_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | list[Any] | str | None = None
    tool_output: Any = None
    tool_is_error: bool = False
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    user_facing_output: bool = False
    # Optional chat history for rules that need messages (repair_loop).
    messages: list[dict[str, Any]] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any] = field(default_factory=dict)
    # When True, persist fuller tool_input (debug only — default redacts).
    debug: bool = False

    def __post_init__(self) -> None:
        if not self.host_session_id:
            raise ValueError("AdapterEvent.host_session_id is required")
        if not self.agent_id:
            self.agent_id = "main"
        if self.parent_session_id is None:
            self.parent_session_id = self.host_session_id


@dataclass
class Decision:
    """Host-agnostic outcome of evaluating one AdapterEvent."""

    action: DecisionAction
    reason: str
    status: RuntimeStatus
    hits: list[WasteHit] = field(default_factory=list)
    agent_id: str = "main"
    host_session_id: str = ""
    # Optional pre-shaped blob for a specific host (Claude hook JSON, etc.).
    host_response: dict[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        """JSON-serializable form for sidecar HTTP responses."""
        return {
            "decision": self.action.value,
            "reason": self.reason,
            "status": self.status.value,
            "agent_id": self.agent_id,
            "host_session_id": self.host_session_id,
            "events": [
                {
                    "type": h.type,
                    "rule": h.rule,
                    "confidence": h.confidence,
                    "estimated_burn": h.estimated_burn if h.show_burn() else None,
                    "agent_id": h.agent_id,
                    "suggested_action": h.suggested_action,
                    "evidence_keys": list(h.evidence_keys),
                }
                for h in self.hits
            ],
            "host_response": self.host_response,
        }


PresetName = Literal["observe", "alert", "strict"]
