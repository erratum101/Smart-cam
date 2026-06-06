"""Shared Qt theme and scrollbar (used by gui + horizontal_main)."""

from __future__ import annotations

import base64
import ctypes
import sys
from io import BytesIO

from ctypes import wintypes

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QScrollBar,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)

def _colorref_rgb(r: int, g: int, b: int) -> int:
    """Win32 COLORREF: 0x00bbggrr (младший байт — красный)."""
    return (r & 0xFF) | ((g & 0xFF) << 8) | ((b & 0xFF) << 16)


def apply_windows_caption_brand(window: QWidget) -> None:
    """Windows 11 / Win10 22H2+: цвет заголовка и рамки в стиле приложения (DWM)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
    except (AttributeError, TypeError, ValueError):
        return
    if hwnd == 0:
        return
    brand = _colorref_rgb(0x00, 0x2E, 0xE8)  # #002EE8 — как фон idle
    white = _colorref_rgb(0xFF, 0xFF, 0xFF)
    DWMWA_BORDER_COLOR = 34
    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36
    try:
        dwm = ctypes.windll.dwmapi
    except OSError:
        return
    h = wintypes.HWND(hwnd)
    for attr, val in (
        (DWMWA_CAPTION_COLOR, brand),
        (DWMWA_BORDER_COLOR, brand),
        (DWMWA_TEXT_COLOR, white),
    ):
        ref = ctypes.c_uint32(val)
        dwm.DwmSetWindowAttribute(
            h,
            ctypes.c_uint32(attr),
            ctypes.byref(ref),
            ctypes.sizeof(ref),
        )


def _spinbox_chevron_png_b64(*, up: bool) -> str:
    w, h = 14, 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    fill = (240, 240, 240, 255)
    if up:
        draw.polygon([(w // 2, 2), (w - 2, h - 2), (2, h - 2)], fill=fill)
    else:
        draw.polygon([(2, 2), (w - 2, 2), (w // 2, h - 2)], fill=fill)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def spinbox_arrow_stylesheet() -> str:
    u = _spinbox_chevron_png_b64(up=True)
    d = _spinbox_chevron_png_b64(up=False)
    return f"""
        QSpinBox::up-arrow {{
            image: url(data:image/png;base64,{u});
            width: 14px;
            height: 10px;
        }}
        QSpinBox::down-arrow {{
            image: url(data:image/png;base64,{d});
            width: 14px;
            height: 10px;
        }}
    """


class PillVerticalScrollBar(QScrollBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setObjectName("PillScrollBar")
        self.setFixedWidth(13)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = self.style()
        cc = QStyle.ComplexControl.CC_ScrollBar
        groove = style.subControlRect(cc, opt, QStyle.SubControl.SC_ScrollBarGroove, self)
        slider = style.subControlRect(cc, opt, QStyle.SubControl.SC_ScrollBarSlider, self)

        painter.setPen(Qt.PenStyle.NoPen)
        if groove.isValid() and groove.width() > 0 and groove.height() > 2:
            painter.setBrush(QColor(255, 255, 255, 35))
            gw = groove.width()
            rx = max(3, min(6, gw // 2))
            painter.drawRoundedRect(groove.adjusted(2, 5, -2, -5), rx, rx)

        if (
            self.isEnabled()
            and slider.isValid()
            and slider.width() > 0
            and slider.height() >= 8
        ):
            painter.setBrush(QColor(0x8A, 0x8A, 0x8A))
            sw = slider.width()
            rx = max(4, min(7, sw // 2 - 1))
            painter.drawRoundedRect(slider.adjusted(2, 1, -2, -1), rx, rx)
        elif not self.isEnabled() and slider.isValid() and slider.height() >= 8:
            painter.setBrush(QColor(0x55, 0x55, 0x55))
            sw = slider.width()
            rx = max(4, min(7, sw // 2 - 1))
            painter.drawRoundedRect(slider.adjusted(2, 1, -2, -1), rx, rx)


def apply_modern_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    bg = QColor(0x22, 0x22, 0x22)
    card = QColor(0x2E, 0x2E, 0x2E)
    text = QColor(0xFF, 0xFF, 0xFF)
    muted = QColor(0xBB, 0xBB, 0xBB)
    accent = QColor(0x00, 0x2E, 0xE8)
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.Base, card)
    pal.setColor(QPalette.AlternateBase, bg)
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Button, card)
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    pal.setColor(QPalette.PlaceholderText, muted)
    app.setPalette(pal)
    app.setStyleSheet(
        """
        QGroupBox {
            font-weight: 600;
            font-size: 13px;
            border: none;
            border-radius: 14px;
            margin-top: 14px;
            padding: 18px 14px 14px 14px;
            background: #2e2e2e;
            color: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: #ffffff;
        }
        QLabel#hint { color: #bbbbbb; font-size: 12px; }
        QLineEdit, QSpinBox {
            background: #333333;
            border: 1px solid #444444;
            border-radius: 10px;
            padding: 9px 12px;
            color: #ffffff;
            min-height: 20px;
        }
        QSpinBox {
            padding-top: 9px;
            padding-bottom: 9px;
            padding-left: 12px;
            padding-right: 30px;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background: transparent;
            border: none;
            width: 26px;
            margin: 0;
            padding: 0;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background: rgba(255, 255, 255, 0.07);
        }
        QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
            background: rgba(255, 255, 255, 0.12);
        }
        QSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            border-top-right-radius: 8px;
        }
        QSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            border-bottom-right-radius: 8px;
        }
        QPushButton {
            border-radius: 12px;
            padding: 11px 20px;
            font-weight: 600;
            font-size: 13px;
        }
        QPushButton#primary {
            background: #002ee8;
            color: #ffffff;
            border: none;
        }
        QPushButton#primary:hover { background: #0038ff; }
        QPushButton#primary:pressed { background: #0028c4; }
        QPushButton#primary:disabled { background: #444444; color: #888888; }
        QPushButton#danger {
            background: #e80000;
            color: #ffffff;
            border: none;
        }
        QPushButton#danger:hover { background: #ff1a1a; }
        QPushButton#danger:pressed { background: #c40000; }
        QPushButton#ghost {
            background: transparent;
            color: #002ee8;
            border: 1px solid #002ee8;
        }
        QScrollArea { border: none; background: transparent; }
        QScrollBar#PillScrollBar {
            background: transparent;
            border: none;
            margin: 0;
            padding: 0;
        }
        QFrame#segShell {
            border: none;
            border-radius: 22px;
            background: #333333;
        }
        QPushButton#segBtn {
            border: none;
            border-radius: 18px;
            padding: 10px 28px;
            font-weight: 600;
            color: #ffffff;
            background: transparent;
        }
        QPushButton#segBtn:checked {
            background: #ffffff;
            color: #222222;
        }
        """
        + spinbox_arrow_stylesheet()
    )
