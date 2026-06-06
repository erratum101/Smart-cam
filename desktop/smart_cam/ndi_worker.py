"""Optional NDI output worker (off unless SMART_CAM_OUTPUT_MODE includes ndi)."""

from __future__ import annotations

import io
import logging
import threading
import time
from collections.abc import Callable

import numpy as np
from PIL import Image

from .frame_store import FrameStore

logger = logging.getLogger(__name__)


class NdiWorker:
    def __init__(
        self,
        frame_store: FrameStore,
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self._frame_store = frame_store
        self._on_state = on_state
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_generation = -1

    def _emit(self, text: str) -> None:
        if self._on_state:
            try:
                self._on_state(text)
            except Exception:
                logger.exception("ndi on_state failed")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_generation = -1
        self._thread = threading.Thread(target=self._run, name="NdiWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        try:
            import NDIlib as ndi
        except Exception:
            self._emit("NDI: ndi-python not installed; output disabled")
            return

        if not ndi.initialize():
            self._emit("NDI: initialize failed")
            return

        send_create = ndi.SendCreate()
        send_create.ndi_name = "Smart Cam NDI"
        sender = ndi.send_create(send_create)
        if sender is None:
            self._emit("NDI: sender create failed")
            ndi.destroy()
            return
        self._emit("NDI output started")

        try:
            while not self._stop.is_set():
                item, generation = self._frame_store.take_latest()
                if item is None or generation == self._last_generation:
                    time.sleep(0.01)
                    continue
                self._last_generation = generation
                try:
                    frame = (
                        item
                        if isinstance(item, np.ndarray)
                        else np.asarray(Image.open(io.BytesIO(bytes(item))).convert("RGB"))
                    )
                    if frame.ndim != 3 or frame.shape[2] != 3:
                        continue
                    vf = ndi.VideoFrameV2()
                    vf.data = np.ascontiguousarray(frame)
                    vf.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBX
                    ndi.send_send_video_v2(sender, vf)
                except Exception:
                    logger.debug("NDI frame send failed", exc_info=True)
                    continue
        finally:
            try:
                ndi.send_destroy(sender)
            except Exception:
                pass
            try:
                ndi.destroy()
            except Exception:
                pass
            self._emit("NDI output stopped")
