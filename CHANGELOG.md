# Changelog

## 0.1.0 — 2026-07-30

- Initial adapter kernel: `AdapterEvent`, `Decision`, `EngineHandle`, presets.
- Per-agent stream isolation via composite `session_id` (`host::agent`).
- Redaction helpers for tool payloads.
- Memory + SQLite session stores (disk fallback building block).
- Session report formatter; CLI version/health stub (`tokensentinel-sidecar`).
- Tests: multi-agent non-pooling, tool_loop, retry_storm strict deny, redaction.
