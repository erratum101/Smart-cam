"""Minimal HTTP discovery server for USB/cable auto-discovery.

The phone (via ADB reverse) hits GET /info on the discovery port and receives
JSON with the stream port and auth token — no QR scan required.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

_DISCOVERY_PATH = "/info"


class DiscoveryServer:
    """Serves ``GET /info`` → ``{"p": stream_port, "t": token, "n": name, "sp"?, "m"?}``.

    Binds only to ``127.0.0.1`` so it is reachable via ADB reverse tunnel but
    not exposed on the LAN (mDNS covers WiFi discovery instead).

    Поля ``sp`` (signaling port) и ``m`` (mode) добавлены, чтобы телефон при
    авто-обнаружении сразу пошёл по WebRTC-пути, а не TCP/JPEG.
    """

    def __init__(
        self,
        discovery_port: int,
        stream_port: int,
        token: str,
        name: str = "",
        signaling_port: int | None = None,
        mode: str | None = None,
        lan_ip: str = "",
    ) -> None:
        self._discovery_port = discovery_port
        self._stream_port = stream_port
        self._token = token
        self._name = name
        self._signaling_port = signaling_port
        self._mode = mode
        self._lan_ip = lan_ip.strip()
        self._lock = threading.Lock()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_token(self, token: str) -> None:
        with self._lock:
            self._token = token

    def set_signaling(self, signaling_port: int | None, mode: str | None) -> None:
        with self._lock:
            self._signaling_port = signaling_port
            self._mode = mode

    def start(self) -> None:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == _DISCOVERY_PATH:
                    with outer._lock:
                        info: dict = {"p": outer._stream_port, "t": outer._token}
                        if outer._name:
                            info["n"] = outer._name
                        if outer._signaling_port is not None:
                            info["sp"] = int(outer._signaling_port)
                        if outer._mode:
                            info["m"] = outer._mode
                        if outer._lan_ip:
                            info["lip"] = outer._lan_ip
                        body = json.dumps(info).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *_args: object) -> None:
                pass  # suppress default HTTP access log

        try:
            srv = HTTPServer(("127.0.0.1", self._discovery_port), _Handler)
        except OSError as exc:
            logger.warning(
                "DiscoveryServer: cannot bind 127.0.0.1:%s — %s",
                self._discovery_port,
                exc,
            )
            return

        self._server = srv
        self._thread = threading.Thread(target=srv.serve_forever, daemon=True)
        self._thread.start()
        logger.info("DiscoveryServer listening on 127.0.0.1:%s", self._discovery_port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
