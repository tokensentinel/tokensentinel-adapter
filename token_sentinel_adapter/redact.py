"""Best-effort redaction for tool payloads.

Not a DLP product — regex/entropy heuristics only. Unit-tested for common
secret shapes; false negatives remain possible.
"""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "[REDACTED]"

# High-signal secret patterns (API keys, tokens, PEM blocks).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT-ish
)

# Long high-entropy-ish tokens (base64-like).
_ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9_\-+/=]{40,}\b")

_MAX_STRING = 2_000
_MAX_DEPTH = 6
_MAX_LIST = 50


def redact_text(text: str) -> str:
    """Redact secret-like substrings and cap length."""
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_REDACTED, out)
    # Entropy pass: only replace tokens that are not mostly path-like.
    def _entropy_sub(m: re.Match[str]) -> str:
        s = m.group(0)
        if "/" in s or s.startswith(".") or s.count("-") > 4:
            return s
        # Skip pure hex short hashes already covered; long blobs go.
        if len(s) >= 40:
            return _REDACTED
        return s

    out = _ENTROPY_TOKEN.sub(_entropy_sub, out)
    if len(out) > _MAX_STRING:
        out = out[:_MAX_STRING] + "…[truncated]"
    return out


def redact_mapping(value: Any, *, depth: int = 0) -> Any:
    """Deep-redact dict/list/str structures for storage and messages."""
    if depth > _MAX_DEPTH:
        return "[MAX_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= _MAX_LIST:
                out["…"] = f"truncated {len(value) - _MAX_LIST} keys"
                break
            key = redact_text(str(k))
            # Known sensitive keys: always redact values.
            if re.search(r"(?i)(password|secret|token|api[_-]?key|authorization|credential)", key):
                out[key] = _REDACTED
            else:
                out[key] = redact_mapping(v, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        items = list(value)[:_MAX_LIST]
        redacted = [redact_mapping(v, depth=depth + 1) for v in items]
        if len(value) > _MAX_LIST:
            redacted.append(f"…[+{len(value) - _MAX_LIST} items]")
        return redacted
    return redact_text(str(value))
