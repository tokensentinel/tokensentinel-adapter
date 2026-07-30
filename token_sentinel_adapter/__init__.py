"""TokenSentinel adapter kernel — host-agnostic harness integration.

Maps host lifecycle events into :class:`~token_sentinel.CallRecord` streams,
runs the shared ``token-sentinel`` rule engine with **per-agent** session
keys, and returns host-agnostic :class:`Decision` values.

Host bridges (Claude Code, Codex, …) live in separate packages/repos and
must not reimplement rules.
"""

from __future__ import annotations

from token_sentinel_adapter.decisions import decision_from_events, format_reason
from token_sentinel_adapter.engine import EngineHandle, EngineResult
from token_sentinel_adapter.normalize import build_call_record, stream_session_id
from token_sentinel_adapter.presets import PRESETS, PresetName, resolve_preset
from token_sentinel_adapter.redact import redact_mapping, redact_text
from token_sentinel_adapter.report import format_session_report
from token_sentinel_adapter.types import (
    AdapterEvent,
    Decision,
    DecisionAction,
    RuntimeStatus,
    WasteHit,
)

__version__ = "0.1.0"

__all__ = [
    "AdapterEvent",
    "Decision",
    "DecisionAction",
    "EngineHandle",
    "EngineResult",
    "PRESETS",
    "PresetName",
    "RuntimeStatus",
    "WasteHit",
    "build_call_record",
    "decision_from_events",
    "format_reason",
    "format_session_report",
    "redact_mapping",
    "redact_text",
    "resolve_preset",
    "stream_session_id",
    "__version__",
]
