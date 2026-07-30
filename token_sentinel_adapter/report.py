"""Human-readable session reports (UX Stage 7)."""

from __future__ import annotations

from collections import Counter

from token_sentinel_adapter.types import RuntimeStatus, WasteHit


def format_session_report(
    *,
    host_session_id: str,
    mode: str,
    status: RuntimeStatus,
    hits: list[WasteHit],
    tool_call_count: int | None = None,
    cloud: str = "off",
) -> str:
    agents = sorted({h.agent_id for h in hits}) or ["main"]
    by_type = Counter(h.type for h in hits)
    lines = [
        f"Session report · {mode} · status: {status.value} · cloud: {cloud}",
        f"session: {host_session_id}",
    ]
    if tool_call_count is not None:
        lines[0] = (
            f"Session report · {mode} · {tool_call_count} tool calls · "
            f"{len(agents)} agents · status: {status.value} · cloud: {cloud}"
        )
    if not hits:
        lines.append("Caught: (none)")
    else:
        lines.append("Caught:")
        for t, n in by_type.most_common():
            agent_list = sorted({h.agent_id for h in hits if h.type == t})
            agents_s = ", ".join(agent_list)
            lines.append(f"  · {t} ×{n}  (agent: {agents_s})")
    return "\n".join(lines)
