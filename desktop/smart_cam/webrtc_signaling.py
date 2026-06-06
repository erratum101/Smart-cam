"""Minimal HTTP signaling server for mobile->desktop WebRTC."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

from aiohttp import web

from .webrtc_receiver import WebRtcSessionManager

logger = logging.getLogger(__name__)


class WebRtcSignalingServer:
    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        session_manager: WebRtcSessionManager,
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._token = token
        self._mgr = session_manager
        self._on_state = on_state
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._stop = threading.Event()

    def _emit(self, text: str) -> None:
        if self._on_state:
            try:
                self._on_state(text)
            except Exception:
                logger.exception("webrtc signaling on_state failed")

    def set_token(self, token: str) -> None:
        self._token = token

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="WebRtcSignaling", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: None)
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_server())
        try:
            while not self._stop.is_set():
                self._loop.run_until_complete(asyncio.sleep(0.2))
        finally:
            self._loop.run_until_complete(self._shutdown())
            self._loop.close()

    async def _start_server(self) -> None:
        app = web.Application()
        app.router.add_post("/webrtc/offer", self._handle_offer)
        app.router.add_get("/webrtc/stats", self._handle_stats)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        self._emit(f"WebRTC signaling on {self._host}:{self._port}")

    async def _shutdown(self) -> None:
        try:
            await self._mgr.close()
        except Exception:
            logger.debug("mgr close failed", exc_info=True)
        if self._site:
            await self._site.stop()
            self._site = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._emit("WebRTC signaling stopped")

    async def _handle_offer(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "bad json"}, status=400)
        token = str(data.get("token", ""))
        if token != self._token:
            return web.json_response({"error": "auth failed"}, status=401)
        sdp = str(data.get("sdp", "")).strip()
        sdp_type = str(data.get("type", "offer")).strip() or "offer"
        if not sdp:
            return web.json_response({"error": "empty sdp"}, status=400)
        try:
            frame_rotate_k = int(data.get("frame_rotate_k", 0))
            sid, answer_sdp = await self._mgr.accept_offer(
                sdp,
                sdp_type=sdp_type,
                frame_rotate_k=frame_rotate_k,
            )
            return web.json_response(
                {
                    "session": sid,
                    "type": "answer",
                    "sdp": answer_sdp,
                }
            )
        except Exception as e:
            logger.exception("accept_offer failed")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_stats(self, request: web.Request) -> web.Response:
        token = request.query.get("token", "")
        if token != self._token:
            return web.json_response({"error": "auth failed"}, status=401)
        return web.json_response(self._mgr.stats())

