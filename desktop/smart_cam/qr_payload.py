"""Compact JSON payload for phone QR scan. Schema v1."""

from __future__ import annotations

import json
import socket
from typing import Any


QR_SCHEMA_VERSION = 2


def _pc_name() -> str:
    """Short hostname of this PC (used as display name in the mobile app)."""
    try:
        return socket.gethostname() or ""
    except OSError:
        return ""


def build_connect_payload(
    host: str,
    port: int,
    token: str,
    *,
    mode: str | None = None,
    signaling_port: int | None = None,
    name: str | None = None,
) -> str:
    """Return minified JSON string encoded in the QR code."""
    obj: dict[str, Any] = {
        "v": QR_SCHEMA_VERSION,
        "h": host,
        "p": port,
        "t": token,
    }
    if mode:
        obj["m"] = mode
    if signaling_port is not None:
        obj["sp"] = int(signaling_port)
    n = name if name is not None else _pc_name()
    if n:
        obj["n"] = n
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
