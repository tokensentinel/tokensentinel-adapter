"""SQLite session store for disk fallback."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from token_sentinel import CallRecord

from token_sentinel_adapter.session_store import SqliteSessionStore


def test_sqlite_roundtrip(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "sess.db", max_per_stream=10)
    call = CallRecord(
        session_id="h::main",
        timestamp=datetime.now(timezone.utc),
        provider="claude-code",
        model="m",
        method="tool.Read",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=1.0,
        request_hash="abc",
        tool_calls=[{"name": "Read", "input": {"path": "a.py"}}],
    )
    store.append(call)
    rows = store.list_calls("h::main")
    assert len(rows) == 1
    assert rows[0].session_id == "h::main"
    assert rows[0].tool_calls[0]["name"] == "Read"
