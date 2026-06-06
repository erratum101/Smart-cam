"""Binary protocol v1 — see docs/PROTOCOL.md."""

from __future__ import annotations

import struct
from typing import Final

MAGIC: Final[bytes] = b"SCWB"
VERSION: Final[int] = 1

TYPE_HELLO: Final[int] = 1
TYPE_HELLO_OK: Final[int] = 2
TYPE_FRAME: Final[int] = 3
TYPE_SERVER_SESSION: Final[int] = 4
TYPE_CLIENT_SESSION: Final[int] = 5
TYPE_ERROR: Final[int] = 255

ERR_AUTH_FAILED: Final[int] = 1
ERR_BAD_MESSAGE: Final[int] = 2
ERR_SERVER_ERROR: Final[int] = 3

HEADER_STRUCT = struct.Struct("!4sBBI")  # magic 4, ver u8, type u8, length u32 BE


def pack_message(msg_type: int, body: bytes = b"") -> bytes:
    if len(MAGIC) != 4:
        raise ValueError("magic must be 4 bytes")
    return HEADER_STRUCT.pack(MAGIC, VERSION, msg_type, len(body)) + body


def parse_header(data: bytes) -> tuple[int, int, int]:
    if len(data) != HEADER_STRUCT.size:
        raise ValueError("bad header size")
    magic, ver, msg_type, length = HEADER_STRUCT.unpack(data)
    if magic != MAGIC:
        raise ValueError("bad magic")
    if ver != VERSION:
        raise ValueError("bad version")
    return msg_type, length


def pack_hello_ok(stream_quality: int = 2, *, session_live: bool = False) -> bytes:
    """HELLO_OK body: quality u8 (0..2), session_live u8 (1=ПК в режиме трансляции)."""
    q = max(0, min(2, int(stream_quality)))
    live = 1 if session_live else 0
    return pack_message(TYPE_HELLO_OK, bytes([q, live]))


def pack_server_session(live: bool) -> bytes:
    return pack_message(TYPE_SERVER_SESSION, bytes([1 if live else 0]))


def pack_client_session(live: bool) -> bytes:
    return pack_message(TYPE_CLIENT_SESSION, bytes([1 if live else 0]))


def pack_error(code: int, message: str = "") -> bytes:
    msg_bytes = message.encode("utf-8")
    if len(msg_bytes) > 65535:
        msg_bytes = msg_bytes[:65535]
    body = struct.pack("!HH", code, len(msg_bytes)) + msg_bytes
    return pack_message(TYPE_ERROR, body)


def parse_error_body(body: bytes) -> tuple[int, str]:
    if len(body) < 4:
        return ERR_BAD_MESSAGE, "short error body"
    code, mlen = struct.unpack("!HH", body[:4])
    rest = body[4:]
    if len(rest) < mlen:
        return code, rest.decode("utf-8", errors="replace")
    return code, rest[:mlen].decode("utf-8", errors="replace")


def parse_frame_body(body: bytes) -> tuple[int, int, bytes]:
    if len(body) < 12:
        raise ValueError("frame body too short")
    w, h, jlen = struct.unpack("!III", body[:12])
    jpeg = body[12 : 12 + jlen]
    if len(jpeg) != jlen:
        raise ValueError("jpeg length mismatch")
    return w, h, jpeg
