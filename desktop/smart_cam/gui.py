"""PySide6 entry — horizontal main window (preview / QR, settings drawer)."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .horizontal_main import MainWindow, desktop_icon_path
from .theme_widgets import apply_modern_theme


def _request_windows_firewall(parent: MainWindow) -> None:
    if sys.platform != "win32":
        return
    from .win_firewall import (
        DEFAULT_TCP_PORTS,
        _is_admin,
        ensure_windows_firewall_rules,
        firewall_rules_configured,
    )

    if firewall_rules_configured(DEFAULT_TCP_PORTS):
        return

    # Собранный .exe с манифестом admin — правила без лишнего диалога.
    if _is_admin():
        ok, msg = ensure_windows_firewall_rules(allow_uac_elevate=False)
        if not ok:
            QMessageBox.warning(
                parent,
                "Smart Cam — брандмауэр",
                msg or "Не удалось настроить брандмауэр.",
            )
        return

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Smart Cam — брандмауэр Windows")
    box.setText(
        "Для трансляции по Wi‑Fi (WebRTC) Windows должен пропускать входящие "
        "соединения к Smart Cam."
    )
    box.setInformativeText(
        "Будут разрешены:\n"
        "• TCP — порты потока, сигналинга и USB-обнаружения (17777, 17778, 17776);\n"
        "• UDP и TCP — для этого приложения (случайные порты WebRTC).\n\n"
        "Нажмите «Разрешить» и подтвердите запрос UAC (права администратора)."
    )
    allow_btn = box.addButton("Разрешить", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Позже", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is not allow_btn:
        return

    ok, msg = ensure_windows_firewall_rules()
    if ok:
        if msg and "уже настроены" not in msg.lower():
            QMessageBox.information(parent, "Smart Cam — брандмауэр", msg)
        return
    QMessageBox.warning(
        parent,
        "Smart Cam — брандмауэр",
        msg
        or "Не удалось добавить правила. Разрешите Smart Cam вручную "
        "в «Брандмауэр Защитника Windows» для частной сети.",
    )


def run_app() -> int:
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    apply_modern_theme(app)
    ip = desktop_icon_path()
    if ip is not None:
        app.setWindowIcon(QIcon(str(ip)))
    win = MainWindow()
    _request_windows_firewall(win)
    win.show()
    win.raise_()
    win.activateWindow()
    return app.exec()
