"""Entry: python main.py from desktop/."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _early_boot_log(msg: str) -> None:
    """Лог старта: рядом с exe (удобно при onefile) и в %LOCALAPPDATA%\\Smart Cam App\\."""
    try:
        from datetime import datetime

        line = f"{datetime.now().isoformat()} {msg}\n"
        paths: list[Path] = []
        try:
            exe_parent = Path(sys.executable).resolve().parent
            paths.append(exe_parent / "SmartCam_boot.log")
        except OSError:
            pass
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or ".")
        paths.append(base / "Smart Cam App" / "early_boot.log")
        for p in paths:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                continue
    except OSError:
        pass


def _maybe_debug_popup() -> None:
    """SMART_CAM_DEBUG_POPUP=1 — окно до импорта Qt; рядом с exe пишется маркер (если Python дошёл сюда)."""
    if sys.platform != "win32":
        return
    raw = os.environ.get("SMART_CAM_DEBUG_POPUP", "")
    if raw.strip() not in ("1", "true", "yes"):
        return
    try:
        marker = Path(sys.executable).resolve().parent / "SmartCam_python_reached_popup.txt"
        marker.write_text(
            "Interpreter reached _maybe_debug_popup (before MessageBox).\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            "Python в exe запущен. Дальше грузятся Qt и окно.",
            "Smart Cam (debug)",
            0,
        )
    except Exception:
        pass


def _report_startup_failure(exc: BaseException) -> None:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or ".")
    log_dir = base / "Smart Cam App"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "startup_error.log"
        log_path.write_text(text, encoding="utf-8")
    except OSError:
        log_path = Path(os.environ.get("TEMP", ".")) / "smart_cam_app_startup_error.log"
        try:
            log_path.write_text(text, encoding="utf-8")
        except OSError:
            log_path = _root / "startup_error.log"
            log_path.write_text(text, encoding="utf-8")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Startup failed. Log:\n{log_path}",
                "Smart Cam App",
                0x10,
            )
        except Exception:
            pass


def _is_windows_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ensure_admin_on_windows() -> None:
    """Request admin on Windows.

    Rely on Nuitka manifest (--windows-uac-admin) for compiled .exe.
    Do not relaunch at runtime to avoid fragile start behavior.
    """
    if sys.platform != "win32":
        return
    if _is_windows_admin():
        return
    _early_boot_log("not elevated; continue (manifest handles .exe elevation)")


if __name__ == "__main__":
    exit_code = 1
    _early_boot_log("main: start")
    _ensure_admin_on_windows()
    _maybe_debug_popup()
    try:
        from smart_cam.qt_env import append_launch_log, prepare_qt_environment

        append_launch_log("bootstrap")
        prepare_qt_environment()
        append_launch_log("qt_env ok")
        from smart_cam.gui import run_app

        append_launch_log("import gui ok")
        exit_code = run_app()
        append_launch_log(f"run_app returned {exit_code}")
    except BaseException as e:
        if isinstance(e, (SystemExit, KeyboardInterrupt)):
            raise
        try:
            from smart_cam.qt_env import append_launch_log

            append_launch_log(f"FATAL {type(e).__name__}: {e!r}")
        except Exception:
            pass
        _report_startup_failure(e)
        exit_code = 1
    sys.exit(exit_code)
