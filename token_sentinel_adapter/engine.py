"""EngineHandle — single entry for host bridges (architecture Layer 2)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from token_sentinel import CallRecord, LeakDetected, LeakEvent, Sentinel

from token_sentinel_adapter.decisions import decision_from_events
from token_sentinel_adapter.normalize import build_call_record, stream_session_id
from token_sentinel_adapter.presets import Preset, resolve_preset
from token_sentinel_adapter.session_store import MemorySessionStore, SessionStore
from token_sentinel_adapter.types import (
    AdapterEvent,
    Decision,
    DecisionAction,
    RuntimeStatus,
    WasteHit,
)


@dataclass
class EngineResult:
    """Outcome of :meth:`EngineHandle.handle`."""

    decision: Decision
    call: CallRecord | None
    events: list[LeakEvent] = field(default_factory=list)


class EngineHandle:
    """Owns one :class:`Sentinel` and evaluates :class:`AdapterEvent`s.

    Per-agent isolation (D10): each ``(host_session_id, agent_id)`` maps to a
    distinct ``CallRecord.session_id`` via :func:`stream_session_id`. Concurrent
    ``handle`` calls for different agents take different locks.
    """

    def __init__(
        self,
        *,
        project: str = "coding-agent",
        preset: str | Preset = "observe",
        cloud_endpoint: str | None = None,
        api_key: str | None = None,
        store: SessionStore | None = None,
        status: RuntimeStatus = RuntimeStatus.HEALTHY,
        extra_config: dict[str, Any] | None = None,
        # When False, never DENY even if preset is strict (e.g. degraded path).
        allow_block: bool | None = None,
    ) -> None:
        self.project = project
        if isinstance(preset, Preset):
            self.preset = preset
        else:
            self.preset = resolve_preset(preset)

        config = dict(self.preset.config)
        if extra_config:
            config.update(extra_config)

        # Policy plane disabled at adapter layer for v0 (local harness first).
        # Cloud event sink still works when cloud_endpoint + api_key are set.
        self.sentinel = Sentinel(
            project=project,
            mode=self.preset.mode,
            rules=self.preset.rules,
            config=config,
            cloud_endpoint=cloud_endpoint,
            api_key=api_key,
            policy_endpoint=None,
        )

        self.store: SessionStore = store or MemorySessionStore()
        self._status = status
        self._allow_block = (
            allow_block
            if allow_block is not None
            else (self.preset.mode == "block" and status == RuntimeStatus.HEALTHY)
        )
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._hits_by_stream: dict[str, list[WasteHit]] = {}

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    def set_status(self, status: RuntimeStatus) -> None:
        self._status = status
        # Strict deny only when healthy (architecture D3 / UX).
        if status != RuntimeStatus.HEALTHY:
            self._allow_block = False
        elif self.preset.mode == "block":
            self._allow_block = True

    def _lock_for(self, stream_id: str) -> threading.RLock:
        with self._locks_guard:
            lock = self._locks.get(stream_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[stream_id] = lock
            return lock

    def handle(self, event: AdapterEvent) -> EngineResult:
        """Evaluate one host event. Never raises into the host bridge.

        Fail-open: on internal errors return ALLOW with status DOWN/DEGRADED.
        """
        agent_id = event.agent_id or "main"
        host_session_id = event.host_session_id
        stream_id = stream_session_id(host_session_id, agent_id)

        # Events that do not produce tool/LLM calls still allowed.
        if event.host_event in {
            "SessionStart",
            "SessionEnd",
            "SubagentStart",
            "SubagentStop",
        } and not event.tool_name:
            return EngineResult(
                decision=Decision(
                    action=DecisionAction.ALLOW,
                    reason="",
                    status=self._status,
                    hits=[],
                    agent_id=agent_id,
                    host_session_id=host_session_id,
                ),
                call=None,
                events=[],
            )

        lock = self._lock_for(stream_id)
        try:
            with lock:
                return self._handle_locked(event, stream_id, host_session_id, agent_id)
        except Exception as exc:  # noqa: BLE001 — host must never crash
            return EngineResult(
                decision=Decision(
                    action=DecisionAction.ALLOW,
                    reason=f"TokenSentinel internal error (fail-open): {type(exc).__name__}",
                    status=RuntimeStatus.DEGRADED,
                    hits=[],
                    agent_id=agent_id,
                    host_session_id=host_session_id,
                ),
                call=None,
                events=[],
            )

    def _handle_locked(
        self,
        event: AdapterEvent,
        stream_id: str,
        host_session_id: str,
        agent_id: str,
    ) -> EngineResult:
        call = build_call_record(event)
        assert call.session_id == stream_id

        events: list[LeakEvent] = []
        try:
            events = list(self.sentinel.record_call(call))
        except LeakDetected as blocked:
            # mode=block: engine raises after handlers; treat as deny.
            events = [blocked.event]
            self.store.append(call)
            decision = decision_from_events(
                events,
                mode="block",
                status=self._status,
                host_session_id=host_session_id,
                agent_id=agent_id,
                block_on_waste=self._allow_block,
            )
            if not self._allow_block:
                # Degraded/observe override: annotate only.
                decision.action = DecisionAction.ANNOTATE
            self._remember_hits(stream_id, decision.hits)
            return EngineResult(decision=decision, call=call, events=events)

        self.store.append(call)
        decision = decision_from_events(
            events,
            mode=self.preset.mode,
            status=self._status,
            host_session_id=host_session_id,
            agent_id=agent_id,
            block_on_waste=self._allow_block and self.preset.mode == "block",
        )
        self._remember_hits(stream_id, decision.hits)
        return EngineResult(decision=decision, call=call, events=events)

    def _remember_hits(self, stream_id: str, hits: list[WasteHit]) -> None:
        if not hits:
            return
        buf = self._hits_by_stream.setdefault(stream_id, [])
        buf.extend(hits)
        if len(buf) > 100:
            del buf[:-100]

    def hits_for(
        self, host_session_id: str, agent_id: str = "main"
    ) -> list[WasteHit]:
        sid = stream_session_id(host_session_id, agent_id)
        return list(self._hits_by_stream.get(sid, []))

    def all_hits_for_host_session(self, host_session_id: str) -> list[WasteHit]:
        prefix = f"{host_session_id}::"
        out: list[WasteHit] = []
        for sid, hits in self._hits_by_stream.items():
            if sid.startswith(prefix) or sid == f"{host_session_id}::main":
                out.extend(hits)
        return out
