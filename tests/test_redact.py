"""Redaction unit tests (release hygiene check: redaction-unit)."""

from __future__ import annotations

from token_sentinel_adapter.redact import redact_mapping, redact_text


def test_redact_openai_key() -> None:
    s = "token=sk-abcdefghijklmnopqrstuvwxyz0123456789"
    out = redact_text(s)
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in out
    assert "REDACTED" in out


def test_redact_anthropic_key() -> None:
    s = "sk-ant-" + ("x" * 40)
    assert "sk-ant-" not in redact_text(s) or "REDACTED" in redact_text(s)


def test_redact_mapping_sensitive_key() -> None:
    data = {"api_key": "super-secret-value-here", "path": "/tmp/foo"}
    out = redact_mapping(data)
    assert out["api_key"] == "[REDACTED]"
    assert out["path"] == "/tmp/foo"
