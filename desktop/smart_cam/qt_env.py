"""Qt paths and attributes before any QtWidgets import (critical for frozen/onefile builds)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def prepare_qt_environment() -> None:
    """Point Qt at bundled plugins before QApplication/QtWidgets load."""
    try:
        import PySide6
    except ImportError as e:
        raise RuntimeError(f"PySide6 is not available: {e}") from e

    root = Path(PySide6.__file__).resolve().parent
    # Windows: иначе Qt6*.dll из каталога PySide6 иногда не находятся (Nuitka onefile / Store Python).
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        for sub in (root, root / "bin"):
            if sub.is_dir():
                try:
                    os.add_dll_directory(str(sub))
                except OSError:
                    pass

    plugins = root / "plugins"
    platforms = plugins / "platforms"

    if platforms.is_dir():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms)
    if plugins.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(plugins)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    from PySide6.QtCore import QCoreApplication

    if plugins.is_dir():
        QCoreApplication.addLibraryPath(str(plugins))


def launch_log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or ".")
    d = base / "Smart Cam App"
    d.mkdir(parents=True, exist_ok=True)
    return d / "launch.log"


def append_launch_log(message: str) -> None:
    try:
        from datetime import datetime

        line = f"{datetime.now().isoformat()} {message}\n"
        with launch_log_path().open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        try:
            p = Path(os.environ.get("TEMP", ".")) / "smart_cam_app_launch.log"
            with p.open("a", encoding="utf-8") as f:
                f.write(f"{message}\n")
        except OSError:
            pass

