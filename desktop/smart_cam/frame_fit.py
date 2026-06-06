"""Normalize incoming RGB frames to landscape output size (default 1280×720, low latency)."""

from __future__ import annotations

import io
import os

import numpy as np

TARGET_WIDTH = int(os.environ.get("SMART_CAM_FRAME_WIDTH", "1280"))
TARGET_HEIGHT = int(os.environ.get("SMART_CAM_FRAME_HEIGHT", "720"))


def _apply_rotate_k(arr: np.ndarray, rotate_k: int) -> np.ndarray:
    k = int(rotate_k) % 4
    if k == 0:
        return arr
    return np.rot90(arr, k=k)


def fit_rgb_1920x1080(rgb: np.ndarray, *, rotate_k: int = 0) -> np.ndarray:
    """
    Landscape output at TARGET_WIDTH×TARGET_HEIGHT (default 1280×720).

    Имя функции сохранено для совместимости; для 1080p задайте
    SMART_CAM_FRAME_WIDTH=1920 и SMART_CAM_FRAME_HEIGHT=1080.
    """
    from PIL import Image

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"expected HxWx3 RGB, got {rgb.shape!r}")
    arr = rgb if rgb.flags["C_CONTIGUOUS"] else np.ascontiguousarray(rgb)
    arr = _apply_rotate_k(arr, rotate_k)
    h, w = arr.shape[:2]
    if h > w:
        arr = np.rot90(arr, k=-1)
        h, w = arr.shape[:2]
    tw, th = TARGET_WIDTH, TARGET_HEIGHT
    if w == tw and h == th:
        return arr

    scale = max(tw / float(w), th / float(h))
    new_w = max(tw, int(round(w * scale)))
    new_h = max(th, int(round(h * scale)))
    if new_w == w and new_h == h:
        pil = Image.fromarray(arr, mode="RGB")
    else:
        pil = Image.fromarray(arr, mode="RGB").resize(
            (new_w, new_h), Image.Resampling.BILINEAR
        )
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    box = (left, top, left + tw, top + th)
    return np.asarray(pil.crop(box), dtype=np.uint8)


def fit_jpeg_bytes(jpeg: bytes, *, rotate_k: int = 0) -> np.ndarray:
    """Decode JPEG and normalize like WebRTC (rotate_k + landscape crop/scale)."""
    from PIL import Image

    pil = Image.open(io.BytesIO(jpeg)).convert("RGB")
    return fit_rgb_1920x1080(np.asarray(pil, dtype=np.uint8), rotate_k=rotate_k)
