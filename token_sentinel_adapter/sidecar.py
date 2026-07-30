"""Minimal sidecar entrypoint stub (Phase B will flesh out HTTP server).

For kernel 0.1.0 this module exposes a CLI that validates the package is
importable and prints version metadata for support (release hygiene §9).
"""

from __future__ import annotations

import argparse
import json
import sys

from token_sentinel_adapter import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tokensentinel-sidecar")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print kernel version JSON and exit",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Print health stub (no HTTP server in 0.1.0)",
    )
    parser.parse_args(argv)

    try:
        import token_sentinel as ts

        sdk_version = getattr(ts, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        sdk_version = "unavailable"

    payload = {
        "adapter_version": __version__,
        "sdk_version": sdk_version,
        "status": "healthy",
        "http_server": False,
        "note": "HTTP sidecar lands in Phase B; kernel evaluate path is EngineHandle",
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
