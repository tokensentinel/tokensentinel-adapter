"""Session record persistence for disk-fallback path."""

from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from token_sentinel import CallRecord

from token_sentinel_adapter.normalize import stream_session_id


def _call_to_row(call: CallRecord) -> dict[str, Any]:
    d = asdict(call)
    ts = d.get("timestamp")
    if isinstance(ts, datetime):
        d["timestamp"] = ts.isoformat()
    return d


def _row_to_call(d: dict[str, Any]) -> CallRecord:
    ts = d.get("timestamp")
    if isinstance(ts, str):
        d["timestamp"] = datetime.fromisoformat(ts)
    # Defensive defaults for forward-compat fields.
    d.setdefault("usage_extra", {})
    d.setdefault("tags", {})
    d.setdefault("tool_calls", [])
    d.setdefault("raw_request", {})
    d.setdefault("raw_response_meta", {})
    return CallRecord(**{k: d[k] for k in CallRecord.__dataclass_fields__ if k in d})


class SessionStore(ABC):
    """Persist CallRecords keyed by stream session id."""

    @abstractmethod
    def append(self, call: CallRecord) -> None: ...

    @abstractmethod
    def list_calls(self, stream_session_id: str, *, limit: int = 200) -> list[CallRecord]: ...

    @abstractmethod
    def clear_stream(self, stream_session_id: str) -> None: ...


class MemorySessionStore(SessionStore):
    """In-process store (used alongside live Sentinel; mainly for tests/report)."""

    def __init__(self, *, max_per_stream: int = 200) -> None:
        self._max = max_per_stream
        self._data: dict[str, list[CallRecord]] = {}
        self._lock = threading.Lock()

    def append(self, call: CallRecord) -> None:
        with self._lock:
            buf = self._data.setdefault(call.session_id, [])
            buf.append(call)
            if len(buf) > self._max:
                del buf[: len(buf) - self._max]

    def list_calls(self, stream_session_id: str, *, limit: int = 200) -> list[CallRecord]:
        with self._lock:
            buf = self._data.get(stream_session_id, [])
            return list(buf[-limit:])

    def clear_stream(self, stream_session_id: str) -> None:
        with self._lock:
            self._data.pop(stream_session_id, None)

    def all_stream_ids(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())


class SqliteSessionStore(SessionStore):
    """SQLite WAL store for degraded path rehydration."""

    def __init__(self, path: str | Path, *, max_per_stream: int = 200) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._max = max_per_stream
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # timeout + busy_timeout matter across OS processes (Claude parallel tools),
        # not only threads within one process.
        conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS calls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stream_id TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_calls_stream ON calls(stream_id, id)"
                )
                conn.commit()
            finally:
                conn.close()

    def append(self, call: CallRecord) -> None:
        payload = json.dumps(_call_to_row(call), default=str)
        with self._lock:
            conn = self._connect()
            try:
                # Cross-process writers: take a reserved lock for the write txn.
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO calls (stream_id, payload, created_at) VALUES (?, ?, ?)",
                    (call.session_id, payload, call.timestamp.isoformat()),
                )
                # Truncate old rows for this stream.
                conn.execute(
                    """
                    DELETE FROM calls WHERE stream_id = ? AND id NOT IN (
                        SELECT id FROM calls WHERE stream_id = ?
                        ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (call.session_id, call.session_id, self._max),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def list_calls(self, stream_session_id: str, *, limit: int = 200) -> list[CallRecord]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT payload FROM calls WHERE stream_id = ?
                    ORDER BY id ASC
                    """,
                    (stream_session_id,),
                ).fetchall()
            finally:
                conn.close()
        calls = [_row_to_call(json.loads(r[0])) for r in rows]
        return calls[-limit:]

    def clear_stream(self, stream_session_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM calls WHERE stream_id = ?", (stream_session_id,))
                conn.commit()
            finally:
                conn.close()


def stream_id_for(host_session_id: str, agent_id: str) -> str:
    return stream_session_id(host_session_id, agent_id)
