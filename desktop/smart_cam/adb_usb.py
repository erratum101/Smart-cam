"""Автоматический проброс TCP с телефона на ПК через adb reverse (режим USB / Cable)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _subprocess_kwargs() -> dict:
    kw: dict = {"timeout": 20, "capture_output": True, "text": True}
    if sys.platform == "win32":
        # Без всплывающего консольного окна на Windows (Python 3.7+).
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if flags:
            kw["creationflags"] = flags
    return kw


def resolve_adb_executable() -> str | None:
    """
    Путь к adb.

    Сначала явный override, затем **platform-tools из Android SDK** — чтобы не брать
    чужой ``adb`` из PATH (например DroidCam OBS), который ломает демон на :5037.
    В конце — первый ``adb`` из PATH.
    """
    override = os.environ.get("SMARTCAM_ADB", "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return str(p)
    name = "adb.exe" if sys.platform == "win32" else "adb"
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(key)
        if not root:
            continue
        cand = Path(root) / "platform-tools" / name
        if cand.is_file():
            return str(cand)
    if sys.platform == "win32":
        lad = os.environ.get("LOCALAPPDATA")
        if lad:
            cand = Path(lad) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
            if cand.is_file():
                return str(cand)
    return shutil.which("adb")


def adb_reverse_tcp(port: int) -> tuple[bool, str]:
    """
    Выполняет ``adb reverse tcp:{port} tcp:{port}``.
    Возвращает (успех, краткое сообщение для лога или UI).
    """
    adb = resolve_adb_executable()
    if not adb:
        return False, "adb not found (install Platform Tools or add to PATH)"
    cmd = [adb, "reverse", f"tcp:{port}", f"tcp:{port}"]
    try:
        r = subprocess.run(cmd, **_subprocess_kwargs())
    except subprocess.TimeoutExpired:
        return False, "adb reverse timed out"
    except OSError as e:
        logger.warning("adb reverse failed: %s", e)
        return False, str(e)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode == 0:
        msg = out or err or "ok"
        logger.info("adb reverse tcp:%s -> %s", port, msg)
        return True, msg
    detail = err or out or f"exit {r.returncode}"
    logger.warning("adb reverse failed: %s", detail)
    return False, detail


def adb_reverse_remove(port: int) -> None:
    """Снимает проброс ``tcp:{port}`` (ошибки игнорируются)."""
    adb = resolve_adb_executable()
    if not adb:
        return
    cmd = [adb, "reverse", "--remove", f"tcp:{port}"]
    try:
        subprocess.run(cmd, **_subprocess_kwargs())
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("adb reverse --remove: %s", e)
