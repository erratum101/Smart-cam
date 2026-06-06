"""TCP server: one client, HELLO auth, FRAME queue, session sync with phone."""

from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Callable

from . import protocol as p
from .frame_fit import fit_jpeg_bytes
from .frame_store import FrameStore

logger = logging.getLogger(__name__)


def recv_exact(conn: socket.socket, n: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = n
    while remaining > 0:
        try:
            chunk = conn.recv(remaining)
        except OSError:
            return None
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class StreamServer:
    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        frame_store: FrameStore,
        on_state: Callable[[str], None] | None = None,
        on_jpeg_frame: Callable[[object], None] | None = None,
        on_phone_session: Callable[[bool], None] | None = None,
        on_client_disconnect: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._token = token
        self._frame_store = frame_store
        self._on_state = on_state
        self._on_jpeg_frame = on_jpeg_frame
        self._on_phone_session = on_phone_session
        self._on_client_disconnect = on_client_disconnect
        self._session_live = threading.Event()
        self._frame_rotate_k = 0
        self._conn_lock = threading.Lock()
        self._client_conn: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._sock: socket.socket | None = None

    def set_token(self, token: str) -> None:
        self._token = token

    def set_pc_session_live(self, live: bool) -> None:
        if live:
            self._session_live.set()
        else:
            self._session_live.clear()

    def send_server_session(self, live: bool) -> None:
        """Сообщить телефону, что режим трансляции на ПК вкл/выкл."""
        with self._conn_lock:
            c = self._client_conn
        if c is None:
            return
        try:
            c.sendall(p.pack_server_session(live))
        except OSError:
            logger.debug("send_server_session failed", exc_info=True)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="StreamServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._conn_lock:
            self._client_conn = None
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _emit(self, text: str) -> None:
        if self._on_state:
            try:
                self._on_state(text)
            except Exception:
                logger.exception("on_state failed")

    def _run(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((self._host, self._port))
            self._sock.listen(1)
            self._sock.settimeout(0.5)
        except OSError as e:
            self._emit(f"Bind failed: {e}")
            return

        self._emit(f"Listening on {self._host}:{self._port}")
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                continue
            conn.settimeout(30.0)
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except OSError:
                pass
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
            except OSError:
                pass
            self._emit(f"Client connected {addr[0]}:{addr[1]}")
            self._handle_client(conn)
            try:
                conn.close()
            except OSError:
                pass
            with self._conn_lock:
                if self._client_conn is conn:
                    self._client_conn = None
            self._emit("Client disconnected")
            if self._on_client_disconnect:
                try:
                    self._on_client_disconnect()
                except Exception:
                    logger.exception("on_client_disconnect")
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass
        self._sock = None
        self._emit("Server stopped")

    def _handle_client(self, conn: socket.socket) -> None:
        self._frame_store.clear()
        self._frame_rotate_k = 0

        raw = recv_exact(conn, p.HEADER_STRUCT.size)
        if raw is None:
            return
        try:
            msg_type, length = p.parse_header(raw)
        except ValueError:
            return
        body = recv_exact(conn, length)
        if body is None:
            return
        if msg_type != p.TYPE_HELLO:
            try:
                conn.sendall(p.pack_error(p.ERR_BAD_MESSAGE, "expected HELLO"))
            except OSError:
                pass
            return
        try:
            if b"\x00" in body:
                nul = body.index(b"\x00")
                client_token = body[:nul].decode("utf-8")
                tail = body[nul + 1 :]
                client_q = tail[0] if tail else 1
                self._frame_rotate_k = int(tail[1]) % 4 if len(tail) >= 2 else 0
            else:
                client_token = body.decode("utf-8")
                client_q = 2
                self._frame_rotate_k = 0
        except UnicodeDecodeError:
            try:
                conn.sendall(p.pack_error(p.ERR_AUTH_FAILED, "invalid token encoding"))
            except OSError:
                pass
            return
        client_q = max(0, min(2, int(client_q)))
        if client_token != self._token:
            try:
                conn.sendall(p.pack_error(p.ERR_AUTH_FAILED, "wrong token"))
            except OSError:
                pass
            return
        pc_live = self._session_live.is_set()
        try:
            conn.sendall(p.pack_hello_ok(client_q, session_live=pc_live))
        except OSError:
            return

        with self._conn_lock:
            self._client_conn = conn

        while not self._stop.is_set():
            raw = recv_exact(conn, p.HEADER_STRUCT.size)
            if raw is None:
                break
            try:
                msg_type, length = p.parse_header(raw)
            except ValueError:
                break
            body = recv_exact(conn, length)
            if body is None:
                break

            if msg_type == p.TYPE_CLIENT_SESSION:
                if len(body) < 1:
                    break
                want = body[0] != 0
                if self._on_phone_session:
                    try:
                        self._on_phone_session(want)
                    except Exception:
                        logger.exception("on_phone_session")
                continue

            if msg_type != p.TYPE_FRAME:
                try:
                    conn.sendall(p.pack_error(p.ERR_BAD_MESSAGE, "expected FRAME"))
                except OSError:
                    pass
                break
            try:
                _w, _h, jpeg = p.parse_frame_body(body)
            except ValueError:
                try:
                    conn.sendall(p.pack_error(p.ERR_BAD_MESSAGE, "bad frame"))
                except OSError:
                    pass
                break

            if not self._session_live.is_set():
                continue

            # Emergency TCP/JPEG path only — latest frame wins, no backlog.
            try:
                rgb = fit_jpeg_bytes(jpeg, rotate_k=self._frame_rotate_k)
            except Exception:
                logger.debug("TCP JPEG normalize failed", exc_info=True)
                continue
            self._frame_store.publish(rgb)
            if self._on_jpeg_frame:
                try:
                    self._on_jpeg_frame(rgb)
                except Exception:
                    logger.debug("on_jpeg_frame failed", exc_info=True)
