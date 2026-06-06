"""Feed pyvirtualcam from latest RGB frame (WebRTC path) or emergency JPEG."""

from __future__ import annotations

import io
import logging
import threading
import time
from collections.abc import Callable

from .frame_fit import TARGET_HEIGHT, TARGET_WIDTH, fit_rgb_1920x1080
from .frame_store import FrameStore

logger = logging.getLogger(__name__)

DEFAULT_VCAM_FPS = 30
# Match frame_fit default (1280×720); override via SMART_CAM_VCAM_*.
DEFAULT_VCAM_WIDTH = TARGET_WIDTH
DEFAULT_VCAM_HEIGHT = TARGET_HEIGHT


class VCamWorker:
    def __init__(
        self,
        frame_store: FrameStore,
        on_state: Callable[[str], None] | None = None,
        fps: int = DEFAULT_VCAM_FPS,
        width: int = DEFAULT_VCAM_WIDTH,
        height: int = DEFAULT_VCAM_HEIGHT,
    ) -> None:
        self._frame_store = frame_store
        self._fps = max(1, min(fps, 120))
        self._width = max(16, min(int(width), 4096))
        self._height = max(16, min(int(height), 4096))
        self._on_state = on_state
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_generation = -1

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_generation = -1
        self._thread = threading.Thread(target=self._run, name="VCamWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _emit(self, text: str) -> None:
        if self._on_state:
            try:
                self._on_state(text)
            except Exception:
                logger.exception("on_state failed")

    def _run(self) -> None:
        try:
            import numpy as np
            from PIL import Image
        except ImportError as e:
            self._emit(f"numpy/Pillow required for virtual camera: {e}")
            return

        try:
            import pyvirtualcam
        except ImportError:
            self._emit("pyvirtualcam not installed")
            return

        width, height = self._width, self._height
        black = np.zeros((height, width, 3), dtype=np.uint8)
        # Reused output buffer — avoid per-frame allocations in the hot path.
        out_buf = np.empty((height, width, 3), dtype=np.uint8)
        cam_ctx: object | None = None
        cam: object | None = None

        try:
            cam_ctx = pyvirtualcam.Camera(width=width, height=height, fps=self._fps)
            cam = cam_ctx.__enter__()
            self._emit(f"Virtual camera {width}×{height} @ {self._fps} fps")
        except Exception as e:
            self._emit(f"Virtual camera error: {e}")
            return

        frame_interval = 1.0 / float(self._fps)
        try:
            while not self._stop.is_set():
                item, generation = self._frame_store.take_latest()
                if item is None or generation == self._last_generation:
                    try:
                        cam.send(black)
                        cam.sleep_until_next_frame()
                    except Exception:
                        time.sleep(frame_interval)
                    continue

                self._last_generation = generation
                try:
                    if not self._fill_buffer(item, out_buf, black, np, Image):
                        cam.send(black)
                    else:
                        cam.send(out_buf)
                    cam.sleep_until_next_frame()
                except Exception:
                    logger.debug("vcam frame failed", exc_info=True)
                    try:
                        cam.send(black)
                        cam.sleep_until_next_frame()
                    except Exception:
                        time.sleep(frame_interval)
        except Exception as e:
            self._emit(f"Virtual camera error: {e}")
        finally:
            if cam_ctx is not None:
                try:
                    cam_ctx.__exit__(None, None, None)
                except Exception:
                    logger.debug("vcam __exit__", exc_info=True)
            self._emit("Virtual camera stopped")

    def _fill_buffer(self, item, out_buf, black, np, Image) -> bool:  # type: ignore[no-untyped-def]
        height, width = out_buf.shape[:2]
        if isinstance(item, np.ndarray):
            frame = item
            if frame.ndim != 3 or frame.shape[2] != 3:
                return False
            try:
                frame = fit_rgb_1920x1080(frame)
            except Exception:
                return False
            if frame.shape[:2] == (height, width):
                np.copyto(out_buf, frame)
                return True
            pil_img = Image.fromarray(frame, mode="RGB").resize(
                (width, height), Image.Resampling.BILINEAR
            )
            np.copyto(out_buf, np.asarray(pil_img, dtype=np.uint8))
            return True

        # Legacy: raw JPEG if server did not normalize (should not happen).
        jpeg = bytes(item)
        try:
            frame = fit_rgb_1920x1080(
                np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"), dtype=np.uint8)
            )
            np.copyto(out_buf, frame)
        except Exception:
            return False
        return True
