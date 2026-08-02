"""Build engine CallRecords from AdapterEvents (per-agent stream keys)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from token_sentinel import CallRecord

from token_sentinel_adapter.redact import redact_mapping
from token_sentinel_adapter.types import AdapterEvent

# Coding-agent tools that behave like retrieval for retrieval_thrash.
DEFAULT_CODING_RETRIEVAL_HINTS: frozenset[str] = frozenset(
    {
        "Grep",
        "Glob",
        "Search",
        "SemanticSearch",
        "WebSearch",
        "find",
        "rg",
    }
)


def stream_session_id(host_session_id: str, agent_id: str | None = None) -> str:
    """Composite session key for rule windows.

    Isolation is achieved
    by giving each agent its own Tracer session string.
    """
    agent = (agent_id or "main").strip() or "main"
    host = host_session_id.strip()
    if not host:
        raise ValueError("host_session_id is required")
    return f"{host}::{agent}"


def parse_stream_session_id(session_id: str) -> tuple[str, str]:
    """Inverse of :func:`stream_session_id`. Returns (host_session_id, agent_id)."""
    if "::" not in session_id:
        return session_id, "main"
    host, _, agent = session_id.partition("::")
    return host, agent or "main"


def _stable_json(obj: Any) -> str:
    try:
        return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        return json.dumps(str(obj), sort_keys=True)


def hash_tool_payload(tool_name: str | None, tool_input: Any) -> str:
    raw = f"{tool_name or ''}|{_stable_json(tool_input)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def estimate_tokens_from_size(text: str | None, *, chars_per_token: float = 4.0) -> int:
    """Rough token estimate for tool output context-pressure signals."""
    if not text:
        return 0
    return max(0, int(len(text) / chars_per_token))


def build_call_record(event: AdapterEvent) -> CallRecord:
    """Map a host-normalized event to a :class:`CallRecord` for the engine."""
    agent_id = event.agent_id or "main"
    session_id = stream_session_id(event.host_session_id, agent_id)

    tool_input = event.tool_input
    if not event.debug:
        tool_input = redact_mapping(tool_input) if tool_input is not None else None

    tool_calls: list[dict[str, Any]] = []
    if event.tool_name:
        tool_calls.append(
            {
                "name": event.tool_name,
                "input": tool_input if tool_input is not None else {},
            }
        )

    prompt_tokens = event.prompt_tokens
    completion_tokens = event.completion_tokens

    # Soft context-pressure: if host gave no usage, estimate from tool output
    # size *before* redaction (redaction collapses long blobs and would hide bloat).
    if prompt_tokens == 0 and event.tool_output is not None:
        out_text = (
            event.tool_output
            if isinstance(event.tool_output, str)
            else _stable_json(event.tool_output)
        )
        est = estimate_tokens_from_size(out_text)
        if est >= 500:
            prompt_tokens = est

    raw_request: dict[str, Any] = {
        "host": event.host,
        "host_event": event.host_event,
        "host_session_id": event.host_session_id,
        "agent_id": agent_id,
        "agent_type": event.agent_type,
        "parent_session_id": event.parent_session_id or event.host_session_id,
        "tool_name": event.tool_name,
        "tool_is_error": event.tool_is_error,
    }
    if event.messages is not None:
        # repair_loop reads messages from raw_request; redact content strings.
        if event.debug:
            raw_request["messages"] = event.messages
        else:
            raw_request["messages"] = redact_mapping(event.messages)

    # Merge non-secret host metadata (already host-controlled).
    if event.raw_payload and event.debug:
        raw_request["raw_payload"] = event.raw_payload

    model = event.model or f"{event.host}-session"
    method = f"tool.{event.tool_name}" if event.tool_name else f"host.{event.host_event}"

    return CallRecord(
        session_id=session_id,
        timestamp=event.timestamp,
        provider=event.host,
        model=model,
        method=method,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=event.latency_ms,
        request_hash=hash_tool_payload(event.tool_name, event.tool_input),
        tool_calls=tool_calls,
        user_facing_output=event.user_facing_output,
        raw_request=raw_request,
        raw_response_meta={},
        tags={
            "environment": "coding-agent",
            "feature": event.host.replace("_", "-")[:64],
            "version": "adapter-0.1.0",
        },
        agent_id=agent_id,
    )
