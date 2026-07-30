"""Presets for harness adapters (observe / alert / strict)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from token_sentinel_adapter.types import PresetName

__all__ = ["PRESETS", "Preset", "PresetName", "resolve_preset"]

# Coding-agent retrieval tool name patterns for retrieval_thrash config.
# The SDK rule matches substrings / globs against tool names.
_CODING_RETRIEVAL_PATTERNS: tuple[str, ...] = (
    "search",
    "grep",
    "glob",
    "find",
    "retrieve",
    "query",
    "lookup",
    "*Search",
    "*Grep",
    "*Glob",
)


@dataclass(frozen=True)
class Preset:
    name: PresetName
    mode: Literal["log", "alert", "block"]
    description: str
    # Extra Sentinel(config=...) keys.
    config: dict[str, Any]
    # Which rules to enable; "all" uses engine defaults then config overlays.
    rules: list[str] | Literal["all"]


# Default live set for coding agents (UX contract): loops, retries, search thrash.
# context_bloat may fire when prompt_tokens estimated from large tool output.
_CODING_RULES: list[str] = [
    "tool_loop",
    "retry_storm",
    "retrieval_thrash",
    "context_bloat",
    "zombie",
]

_CODING_CONFIG: dict[str, Any] = {
    # Slightly more tolerant for agentic coding (exploration is normal).
    "tool_loop.min_calls": 3,
    "tool_loop.window_seconds": 90,
    "retry_storm.min_retries": 5,
    "retry_storm.window_seconds": 45,
    "retrieval_thrash.min_calls": 4,
    "retrieval_thrash.window_seconds": 120,
    # SDK key is retrieval_tool_patterns (substring / glob against tool names).
    "retrieval_thrash.retrieval_tool_patterns": list(_CODING_RETRIEVAL_PATTERNS),
    # Soften context_bloat for estimated tokens from tool dumps.
    "context_bloat.min_turns": 3,
    "context_bloat.lookback_turns": 8,
    "context_bloat.slope_threshold": 2000,
}


PRESETS: dict[PresetName, Preset] = {
    "observe": Preset(
        name="observe",
        mode="log",
        description="Detect and annotate only; never deny host tools.",
        config=dict(_CODING_CONFIG),
        rules=list(_CODING_RULES),
    ),
    "alert": Preset(
        name="alert",
        mode="alert",
        description="Same as observe; mode stamp for cloud/alerting semantics.",
        config=dict(_CODING_CONFIG),
        rules=list(_CODING_RULES),
    ),
    "strict": Preset(
        name="strict",
        mode="block",
        description="Deny subsequent tools when a rule fires (requires healthy sidecar).",
        config=dict(_CODING_CONFIG),
        rules=list(_CODING_RULES),
    ),
}


def resolve_preset(name: str | PresetName) -> Preset:
    key = str(name).strip().lower()
    for pname, preset in PRESETS.items():
        if pname == key:
            return preset
    allowed = ", ".join(sorted(PRESETS))
    raise ValueError(f"Unknown preset {name!r}; expected one of: {allowed}")
