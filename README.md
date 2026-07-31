# token-sentinel-adapter

Host-agnostic **adapter kernel** for [TokenSentinel](https://tokensentinel.dev).

Coding-agent hosts (Claude Code, Codex, and similar) convert vendor-specific events into `AdapterEvent`, call `EngineHandle`, and map `Decision` back to the host.

**Rules live only in [`token-sentinel`](https://pypi.org/project/token-sentinel/).** This package does not reimplement them.

## Install

```bash
pip install token-sentinel-adapter
```

Requires `token-sentinel>=1.0.3,<2`.

For local development against a source checkout of the engine:

```bash
pip install -e /path/to/tokensentinel-sdk-python -e .
```

## Quick start

```python
from token_sentinel_adapter import AdapterEvent, EngineHandle

engine = EngineHandle(project="my-app", preset="observe")  # observe | alert | strict

result = engine.handle(
    AdapterEvent(
        host="claude-code",
        host_event="PostToolUse",
        host_session_id="sess-123",
        agent_id="main",  # use host-provided id for subagents
        tool_name="Read",
        tool_input={"path": "app.py"},
    )
)
print(result.decision.action, result.decision.reason)
print(result.decision.to_wire())
```

## Behavior

| Concern | Behavior |
|---------|----------|
| Multi-agent | Rule windows are per `(host_session_id, agent_id)` — sibling agents do not pool |
| Health | `RuntimeStatus`: `healthy`, `degraded`, or `down` |
| Strict mode | May deny tools only when status is `healthy` |
| Engine | All detection via `token-sentinel` |

### Presets

| Preset | Sentinel mode | Denies tools? |
|--------|---------------|---------------|
| `observe` | log | No |
| `alert` | alert | No |
| `strict` | block | Yes (when healthy) |

Default coding rules: `tool_loop`, `retry_storm`, `retrieval_thrash`, `context_bloat`, `zombie`.

## Status

**0.1.0** — library kernel for host plugins. Optional long-lived HTTP sidecar can be added by host packages as needed.

## License

Apache-2.0
