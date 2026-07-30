# token-sentinel-adapter

**Harness adapter kernel** for [TokenSentinel](https://tokensentinel.dev).

Host bridges (Claude Code, Codex, …) convert vendor-specific hook payloads into
`AdapterEvent`, call `EngineHandle`, and map `Decision` back to the host.
**Rules live only in `token-sentinel`.** This package does not reimplement them.

## Install

```bash
pip install token-sentinel-adapter
# or from a monorepo checkout:
pip install -e ../tokensentinel-sdk-python -e .
```

Requires `token-sentinel>=1.0.3,<2`.

## Quick use

```python
from token_sentinel_adapter import AdapterEvent, EngineHandle

engine = EngineHandle(project="my-app", preset="observe")  # observe | alert | strict

result = engine.handle(
    AdapterEvent(
        host="claude-code",
        host_event="PostToolUse",
        host_session_id="sess-123",
        agent_id="main",  # subagents: host-provided agent_id
        tool_name="Read",
        tool_input={"path": "app.py"},
    )
)
print(result.decision.action, result.decision.reason)
print(result.decision.to_wire())
```

## Design locks (v0)

| ID | Behavior |
|---|---|
| D8 | One multi-tenant engine process; locks per `(session, agent)` |
| D9 | Events carry `host_session_id` + `agent_id` |
| D10 | Rule windows are **per agent** (composite `session_id`) — siblings never pool |
| D11 | `RuntimeStatus` healthy / degraded / down |
| D13 | Python brain only (`token-sentinel`) |
| D14 | Plugins should bootstrap a pinned runtime; end users should not hand-pip |

See repo-root `plugin_architecture_v0.md`, `plugin_ux_journey_v0.md`, `release_hygiene_v0.md`.

## Presets

| Preset | Sentinel mode | Denies tools? |
|---|---|---|
| `observe` | log | No |
| `alert` | alert | No |
| `strict` | block | Yes (only when status is healthy) |

Default coding rules: `tool_loop`, `retry_storm`, `retrieval_thrash`, `context_bloat`, `zombie`.

## Status

**0.1.0** — kernel library. HTTP sidecar server lands with the Claude Code plugin (Phase B).

## License

Apache-2.0
