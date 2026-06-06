"""Horizontal Smart Cam window: top connection overlay; no side panel."""

from __future__ import annotations

import ipaddress
import logging
import math
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
import qrcode
from PIL import Image as PILImage
from PySide6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QElapsedTimer,
    QObject,
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    QSize,
    QSizeF,
    Qt,
    QTimer,
    Signal,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
    QShowEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .adb_usb import adb_reverse_remove, adb_reverse_tcp
from .discovery_server import DiscoveryServer
from .frame_store import FrameStore
from .qr_payload import build_connect_payload
from .server import StreamServer
from .ndi_worker import NdiWorker
from .theme_widgets import apply_windows_caption_brand
from .vcam_worker import VCamWorker
try:
    from .webrtc_receiver import WebRtcSessionManager
    from .webrtc_signaling import WebRtcSignalingServer
except Exception:  # optional runtime deps (aiortc/aiohttp) may be missing
    WebRtcSessionManager = None  # type: ignore[assignment]
    WebRtcSignalingServer = None  # type: ignore[assignment]

try:
    from zeroconf import ServiceInfo, Zeroconf
    _ZEROCONF_AVAILABLE = True
except ImportError:
    _ZEROCONF_AVAILABLE = False

logger = logging.getLogger(__name__)

APP_NAME = "Smart Cam App"
DEFAULT_PORT = 17777
DEFAULT_WEBRTC_SIGNALING_PORT = 17778
# Порт HTTP-обнаружения (USB/ADB): телефон бьёт GET /info через adb reverse.
DEFAULT_DISCOVERY_PORT = 17776
# Фиксированный размер QR на главном экране (idle), без привязки к ширине виджета — не «растёт» от лейаута/ховера.
QR_MAIN_PX = 280
# `secrets.token_urlsafe(12)` → 16 символов; токен и единая ширина трёх полей.
_K_TOKEN_MAX_CHARS = 16
# Одна визуальная ширина у полей «Хост / Порт / Токен» (по длине в символах).
_K_IDLE_FIELD_UNIFORM_CHARS = 12


def _lineedit_w_for_chars(fm: QFontMetrics, n: int, extra: int) -> int:
    if n <= 0:
        return extra
    return fm.horizontalAdvance("W" * n) + extra


def _pixmap_scaled_cover(pix: QPixmap, target: QSize) -> QPixmap:
    """Как BoxFit.cover / object-fit: cover — заполнить область, лишнее обрезать по центру."""
    tw, th = target.width(), target.height()
    if tw <= 0 or th <= 0 or pix.isNull():
        return QPixmap()
    scaled = pix.scaled(
        target,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - tw) // 2)
    y = max(0, (scaled.height() - th) // 2)
    return scaled.copy(QRect(x, y, tw, th))


def _nuitka_compiled() -> bool:
    main = sys.modules.get("__main__")
    return main is not None and getattr(main, "__compiled__", None) is not None


def _desktop_icon_path() -> Path | None:
    names = ("app_icon.png", "icon.png")
    candidates: list[Path] = []
    if getattr(sys, "frozen", False) or _nuitka_compiled():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            candidates.extend(base / n for n in names)
        main_mod = sys.modules.get("__main__")
        main_file = getattr(main_mod, "__file__", None) if main_mod else None
        if main_file:
            base = Path(main_file).resolve().parent
            candidates.extend(base / n for n in names)
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(exe_dir / n for n in names)
    else:
        desktop = Path(__file__).resolve().parent.parent
        for n in names:
            candidates.append(desktop / n)
    for p in candidates:
        if p.is_file():
            return p
    return None


def desktop_icon_path() -> Path | None:
    return _desktop_icon_path()


def _brand_logo_path() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent.parent / "iconnobg.svg",
        Path(__file__).resolve().parent.parent.parent / "iconnobg.svg",
        Path.cwd() / "iconnobg.svg",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _down2_chevron_path() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent.parent / "down2.svg",
        Path(__file__).resolve().parent.parent / "Arrow - Down 2.svg",
        Path(__file__).resolve().parent.parent.parent / "down2.svg",
        Path(__file__).resolve().parent.parent.parent / "Arrow - Down 2.svg",
        Path.cwd() / "down2.svg",
        Path.cwd() / "Arrow - Down 2.svg",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


# PowerShell при каждом _update_qr (таймер 4 с) блокировал GUI — кэш обязателен.
_WIN_NET_CACHE_TTL_SEC = 45.0
_win_net_fetched_at: float = -1000.0
_win_net_cache_ips: list[str] = []
_win_net_cache_gw: frozenset[str] = frozenset()

# Вытаскиваем IPv4 с активных адаптеров и помечаем, есть ли default gateway (Wi‑Fi/Ethernet
# почти всегда есть; VirtualBox Host-Only — нет → не «перебивает» 192.168.56.x в QR).
_PS_WIN_NET_IPV4 = r"""
$seen = @{}
foreach ($cfg in Get-NetIPConfiguration) {
  $ad = $cfg.NetAdapter
  if ($null -eq $ad -or $ad.Status -ne 'Up') { continue }
  $v4 = $cfg.IPv4Address
  if ($null -eq $v4 -or -not $v4.IPAddress) { continue }
  $ip = [string]$v4.IPAddress.Trim()
  if ($ip -eq '') { continue }
  $hasGw = $false
  foreach ($g in @($cfg.IPv4DefaultGateway)) {
    if ($null -ne $g -and $g.NextHop) { $hasGw = $true; break }
  }
  if (-not $seen.ContainsKey($ip)) { $seen[$ip] = $hasGw }
  elseif ($hasGw) { $seen[$ip] = $true }
}
$seen.Keys | Sort-Object | ForEach-Object {
  $tag = if ($seen[$_]) { 'G' } else { 'N' }
  Write-Output ($tag + "`t" + $_)
}
"""


def _win_net_ipv4_scan() -> tuple[list[str], frozenset[str]]:
    """(все IPv4 с Up-адаптеров, подмножество с default gateway). Не-windows: пусто."""
    global _win_net_fetched_at, _win_net_cache_ips, _win_net_cache_gw
    if sys.platform != "win32":
        return [], frozenset()
    now = time.monotonic()
    if (now - _win_net_fetched_at) < _WIN_NET_CACHE_TTL_SEC:
        return list(_win_net_cache_ips), _win_net_cache_gw
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _PS_WIN_NET_IPV4,
            ],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        _win_net_fetched_at = now
        _win_net_cache_ips = []
        _win_net_cache_gw = frozenset()
        return [], frozenset()
    if proc.returncode != 0:
        _win_net_fetched_at = now
        _win_net_cache_ips = []
        _win_net_cache_gw = frozenset()
        return [], frozenset()
    order: list[str] = []
    gw: set[str] = set()
    for ln in proc.stdout.splitlines():
        ln = ln.strip()
        if not ln or "\t" not in ln:
            continue
        tag, ip = ln.split("\t", 1)
        tag, ip = tag.strip().upper(), ip.strip()
        if not ip:
            continue
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        if ip not in order:
            order.append(ip)
        if tag == "G":
            gw.add(ip)
    _win_net_cache_ips = order
    _win_net_cache_gw = frozenset(gw)
    _win_net_fetched_at = now
    return list(_win_net_cache_ips), _win_net_cache_gw


def _qr_lan_tier(ip: str) -> int:
    """
    Меньше = лучше для QR (телефон по Wi‑Fi). 172.17–172.22 часто Docker Desktop / WSL2
    (vEthernet); раньше udp‑трюк отдавал именно их — телефон получал таймаут.
    Подсети host-only/NAT гипервизоров в 192.168.* (напр. 192.168.56.x VirtualBox)
    не доступны с телефона по Wi‑Fi — не даём им тот же приоритет, что реальному LAN.
    """
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return 99
    if a.is_loopback:
        return 99
    if not a.is_private:
        return 98
    if a in ipaddress.ip_network("192.168.0.0/16", strict=False):
        for cidr in (
            "192.168.56.0/24",  # VirtualBox Host-Only (часто «перебивает» udp и QR)
            "192.168.122.0/24",  # libvirt virbr0
            "192.168.234.0/24",  # VMware VMnet8 (типичный NAT)
        ):
            if a in ipaddress.ip_network(cidr, strict=False):
                return 4
        return 0
    if a in ipaddress.ip_network("172.16.0.0/12", strict=False):
        for cidr in (
            # Docker default bridges.
            "172.17.0.0/16",
            "172.18.0.0/16",
            "172.19.0.0/16",
        ):
            if a in ipaddress.ip_network(cidr, strict=False):
                return 4
        return 1
    if a in ipaddress.ip_network("10.0.0.0/8", strict=False):
        # 10/8 often used by VPN overlays (ZeroTier/Tailscale/WireGuard).
        # Keep valid, but below common phone LAN ranges (192.168 / 172.16-31).
        return 2
    return 3


def default_lan_ip() -> str:
    """
    IPv4 для QR в режиме Wi‑Fi. Кандидаты: маршрут к 8.8.8.8 и адреса с имени хоста.
    Не отдаём приоритет «udp» адресу целиком: на Windows он часто vEthernet Docker/WSL.
    """
    udp_ip: str | None = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(0.25)
            s.connect(("8.8.8.8", 80))
            udp_ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        pass

    candidates: list[str] = []

    def add(ip: str) -> None:
        ip = (ip or "").strip()
        if not ip:
            return
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return
        if ip not in candidates:
            candidates.append(ip)

    if udp_ip:
        add(udp_ip)
    try:
        _name, _aliases, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            add(ip)
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        for res in socket.getaddrinfo(
            hostname, None, socket.AF_INET, socket.SOCK_STREAM
        ):
            add(res[4][0])
    except OSError:
        pass
    win_ips, win_gw = _win_net_ipv4_scan()
    for ip in win_ips:
        add(ip)

    if not candidates:
        return "127.0.0.1"

    def is_private_lan(ip: str) -> bool:
        try:
            a = ipaddress.ip_address(ip)
            return a.is_private and not a.is_loopback
        except ValueError:
            return False

    privates = [c for c in candidates if is_private_lan(c)]
    if privates:
        privates.sort(
            key=lambda ip: (
                _qr_lan_tier(ip),
                0 if ip in win_gw else 1,
                0 if ip == udp_ip else 1,
                ip,
            ),
        )
        return privates[0]

    for c in candidates:
        try:
            a = ipaddress.ip_address(c)
            if not a.is_loopback:
                return c
        except ValueError:
            continue
    return "127.0.0.1"


class _RegenIconGlyph(QWidget):
    """Иконка или символ ↻; угол в градусах (Qt: положительный — по часовой)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pm = QPixmap()
        self._text = ""
        self._angle = 0.0
        self._hover_shadow = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
        )

    def set_pixmap(self, pm: QPixmap) -> None:
        self._pm = pm
        self._text = ""
        self.updateGeometry()
        self.update()

    def set_glyph_text(self, s: str) -> None:
        self._text = s
        self._pm = QPixmap()
        self.updateGeometry()
        self.update()

    def _pixmap_logical_size(self) -> QSizeF:
        """Логический (DPR-скорректированный) размер пиксмапа в координатах виджета."""
        if self._pm.isNull():
            return QSizeF(0.0, 0.0)
        try:
            return self._pm.deviceIndependentSize()
        except AttributeError:
            dpr = self._pm.devicePixelRatio() or 1.0
            return QSizeF(self._pm.width() / dpr, self._pm.height() / dpr)

    def sizeHint(self) -> QSize:
        if not self._pm.isNull():
            return self._pixmap_logical_size().toSize()
        if self._text:
            fm = self.fontMetrics()
            return QSize(
                fm.horizontalAdvance(self._text) + 2,
                fm.height() + 2,
            )
        return QSize(22, 22)

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, v: float) -> None:
        if abs(self._angle - v) < 1e-4:
            return
        self._angle = v
        self.update()

    def set_hover_shadow(self, on: bool) -> None:
        if self._hover_shadow == on:
            return
        self._hover_shadow = on
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if not self._pm.isNull():
            # Логические (DPR-скорректированные) размеры пиксмапа: на HiDPI
            # `pm.width()/height()` возвращают физические пиксели, что сдвигает
            # точку отрисовки и ось вращения относительно визуального центра.
            psize = self._pixmap_logical_size()
            iw = psize.width()
            ih = psize.height()
            x = (w - iw) / 2.0
            y = (h - ih) / 2.0
            if self._hover_shadow:
                p.setOpacity(0.24)
                p.drawPixmap(QPointF(x, y + 1), self._pm)
                p.setOpacity(0.14)
                p.drawPixmap(QPointF(x, y + 2), self._pm)
                p.setOpacity(1.0)
            # Вращаем строго вокруг визуального центра иконки (с учётом DPR),
            # чтобы при клике она оставалась на месте и проворачивалась на 360°.
            cx = x + iw / 2.0
            cy = y + ih / 2.0
            p.save()
            p.translate(cx, cy)
            p.rotate(self._angle)
            p.translate(-cx, -cy)
            p.drawPixmap(QPointF(x, y), self._pm)
            p.restore()
        elif self._text:
            if self._hover_shadow:
                p.setPen(QColor(0, 0, 0, 80))
                p.drawText(self.rect().translated(0, 1), Qt.AlignmentFlag.AlignCenter, self._text)
            cx = w / 2.0
            cy = h / 2.0
            p.save()
            p.translate(cx, cy)
            p.rotate(self._angle)
            p.translate(-cx, -cy)
            p.setPen(QColor(255, 255, 255))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
            p.restore()


class _TokenRegenButton(QWidget):
    """↻: без autoraise; при наведении — лёгкая тень у глифа; клик — одно вращение против часовой."""

    def __init__(
        self,
        icon: QIcon,
        outer_side: int,
        on_click: Callable[[], None],
        parent: QWidget | None = None,
        *,
        object_name: str = "",
        tool_tip: str = "",
    ) -> None:
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        if tool_tip:
            self.setToolTip(tool_tip)
        self._on_click = on_click
        self._spin: QVariantAnimation | None = None
        self.setFixedSize(outer_side, outer_side)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

        isz = max(16, int(round(outer_side * 0.56)))
        pm = icon.pixmap(
            QSize(isz, isz), QIcon.Mode.Normal, QIcon.State.Off,
        )
        self._glyph = _RegenIconGlyph(self)
        if pm.isNull():
            f = self._glyph.font()
            f.setPointSize(max(12, isz - 2))
            self._glyph.setFont(f)
            self._glyph.set_glyph_text("↻")
        else:
            self._glyph.set_pixmap(pm)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._glyph, 0, Qt.AlignmentFlag.AlignCenter)

    def _set_glyph_hover_shadow(self, on: bool) -> None:
        self._glyph.set_hover_shadow(on)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._set_glyph_hover_shadow(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_glyph_hover_shadow(False)
        super().leaveEvent(event)

    def _on_spin_done(self) -> None:
        a = self.sender()
        if not isinstance(a, QVariantAnimation):
            return
        end = a.endValue()
        if end is not None:
            self._glyph.set_angle(float(end) % 360.0)

    def _play_spin(self) -> None:
        if self._spin is not None and self._spin.state() == QAbstractAnimation.State.Running:
            self._spin.stop()
        a = (self._glyph.get_angle() % 360.0)
        self._glyph.set_angle(a)
        start = self._glyph.get_angle()
        anim = QVariantAnimation(self)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setDuration(520)
        anim.setStartValue(start)
        # Поворот по часовой стрелке.
        anim.setEndValue(start + 360.0)
        anim.valueChanged.connect(
            lambda v, g=self._glyph: g.set_angle(float(v)),
        )
        anim.finished.connect(self._on_spin_done)
        self._spin = anim
        anim.start()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                self._on_click()
                self._play_spin()
        super().mouseReleaseEvent(event)


class _MainStage(QWidget):
    """Основная область превью/QR."""

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: #002EE8;")

        cv = QVBoxLayout(self)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(stack, stretch=1)


class _BrandIdlePanel(QWidget):
    """Idle screen: blue rings and centered logo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logo = QPixmap()
        self._logo_svg: QSvgRenderer | None = None
        self._center_qr = QPixmap()
        self._center_qr_visible = 0.0
        self._center_qr_target = 0.0
        self._center_swap_duration_sec = 0.36
        self._last_anim_elapsed_ms = 0
        self._anim_clock = QElapsedTimer()
        self._anim_clock.start()
        self._last_anim_elapsed_ms = self._anim_clock.elapsed()
        self._anim_timer = QTimer(self)
        self._anim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim_timer.setInterval(17)  # ~60 Hz (1000/60); PreciseTimer reduces drift on Windows
        self._anim_timer.timeout.connect(self._tick_anim)
        self._anim_timer.start()
        self._ring_hover = 0.0
        self._ring_hover_target = 0.0
        lp = _brand_logo_path()
        if lp is not None:
            if lp.suffix.lower() == ".svg":
                self._logo_svg = QSvgRenderer(str(lp))
            if self._logo_svg is None or not self._logo_svg.isValid():
                self._logo = QIcon(str(lp)).pixmap(512, 512)

    def set_ring_hover_target(self, t: float) -> None:
        """0 = без смещения (равномерное свечение), 1 = смещение «тени» как в макете при наведении."""
        v = max(0.0, min(1.0, t))
        if (v - self._ring_hover_target) ** 2 < 1e-6:
            return
        self._ring_hover_target = v

    def set_center_qr(self, pix: QPixmap | None) -> None:
        """Обновляет пиксмап QR, сам показ управляется set_center_qr_visible()."""
        pm = QPixmap() if pix is None else pix
        if self._center_qr.cacheKey() == pm.cacheKey():
            return
        self._center_qr = pm
        self.update()

    def set_center_qr_visible(self, on: bool) -> None:
        self._center_qr_target = 1.0 if on else 0.0

    def _tick_anim(self) -> None:
        now_ms = self._anim_clock.elapsed()
        dt_sec = max(0.0, min(0.12, (now_ms - self._last_anim_elapsed_ms) / 1000.0))
        self._last_anim_elapsed_ms = now_ms
        d = self._ring_hover_target - self._ring_hover
        if d * d < 1e-6:
            self._ring_hover = self._ring_hover_target
        else:
            self._ring_hover += d * 0.14
        dq = self._center_qr_target - self._center_qr_visible
        if dq * dq < 1e-6:
            self._center_qr_visible = self._center_qr_target
        else:
            step = dt_sec / max(0.001, self._center_swap_duration_sec)
            step = max(0.0, min(1.0, step))
            if dq > 0:
                self._center_qr_visible = min(self._center_qr_target, self._center_qr_visible + step)
            else:
                self._center_qr_visible = max(self._center_qr_target, self._center_qr_visible - step)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QColor("#002EE8"))
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        ring_color = QColor("#002EE8")
        ratios = (1.00, 0.90, 0.80, 0.70, 0.60, 0.50, 0.42, 0.34, 0.26, 0.18)
        base_d = float(self.width())
        t = self._anim_clock.elapsed() / 1000.0
        # fmod keeps the argument to sin small → stable precision; sin is 2π-periodic.
        pulse_phase = math.fmod(t * 1.2, math.tau)
        p.setPen(Qt.PenStyle.NoPen)
        ht = self._ring_hover
        for idx, ratio in enumerate(ratios):
            # Wave animation: each ring pulses with a phase offset.
            wave = math.sin(pulse_phase - idx * 0.55)
            pulse = 1.0 + wave * 0.010
            d = base_d * ratio * pulse
            x = float(cx - d / 2)
            y = float(cy - d / 2)
            # soft blurred shadow: ht=0 — без смещения (симметричное свечение), ht=1 — смещение вниз
            for i in range(1, 6):
                spread = i * 1.4
                alpha = max(1, int(13 - i * 1.5))
                p.setBrush(QColor(0, 0, 0, alpha))
                y0_flat = y - spread
                y0_off = y + 2.0 + spread * 0.28
                y0 = (1.0 - ht) * y0_flat + ht * y0_off
                p.drawEllipse(
                    QRectF(
                        x - spread,
                        y0,
                        d + spread * 2,
                        d + spread * 2,
                    )
                )
            p.setBrush(ring_color)
            p.drawEllipse(QRectF(x, y, d, d))
        # Logo breathes in phase with the smallest ring (same sin argument as last idx in the loop).
        smallest_idx = len(ratios) - 1
        logo_wave = math.sin(pulse_phase - smallest_idx * 0.55)
        logo_pulse = 1.0 + logo_wave * 0.048
        logo_base = max(84.0, base_d * 0.16)
        logo_sz = logo_base * logo_pulse
        half = logo_sz * 0.5
        target = QRectF(cx - half, cy - half, logo_sz, logo_sz)
        mix = max(0.0, min(1.0, self._center_qr_visible))
        # QR заметно меньше логотипа, как просили.
        qr_scale = 0.72
        qr_half = logo_sz * qr_scale * 0.5
        qr_target = QRectF(cx - qr_half, cy - qr_half, qr_half * 2.0, qr_half * 2.0)
        if mix < 0.999:
            p.save()
            p.setOpacity(1.0 - mix)
            if not self._logo.isNull():
                p.drawPixmap(target, self._logo, QRectF(self._logo.rect()))
            elif self._logo_svg is not None and self._logo_svg.isValid():
                self._logo_svg.render(p, target)
            p.restore()
        if mix > 0.001 and not self._center_qr.isNull():
            p.save()
            p.setOpacity(mix)
            p.drawPixmap(qr_target, self._center_qr, QRectF(self._center_qr.rect()))
            p.restore()
        p.end()
        super().paintEvent(event)


class _SegmentSwitch(QWidget):
    """Cable / Wi-fi pill (reference design)."""

    def __init__(
        self,
        on_changed: object,
        *,
        initial_cable: bool = False,
        cable_label: str = "Cable",
        wifi_label: str = "Wi-fi",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        shell = QFrame()
        shell.setObjectName("segShell")
        shell.setFrameShape(QFrame.Shape.NoFrame)
        shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(shell)
        # Inset from outer white border (reference: white selection pill with gap)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(0)
        self._cable = QPushButton(cable_label)
        self._cable.setObjectName("segBtnLeft")
        self._wifi = QPushButton(wifi_label)
        self._wifi.setObjectName("segBtnRight")
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for b in (self._cable, self._wifi):
            b.setCheckable(True)
            b.setFlat(True)
            b.setAutoDefault(False)
            b.setDefault(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            grp.addButton(b)
        self._cable.setChecked(bool(initial_cable))
        self._wifi.setChecked(not bool(initial_cable))
        self._cable.clicked.connect(self._emit)
        self._wifi.clicked.connect(self._emit)
        h.addWidget(self._cable, stretch=1)
        h.addWidget(self._wifi, stretch=1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(shell)

    def _emit(self) -> None:
        self._on_changed(self._cable.isChecked())

    def is_cable(self) -> bool:
        return self._cable.isChecked()

    def set_cable(self, v: bool) -> None:
        self._cable.setChecked(v)
        self._wifi.setChecked(not v)


# Match idle overlay / app blue; label sits on the border to "cut" the stroke
_IDLE_PILL_BG = "#002EE8"
# Inner padding of the white-bordered pill; label x aligns with field text inset
_PILL_INNER_M = (4, 6, 4, 4)  # L, T, R, B
_PILL_LABEL_PAD_H = 4


class _PillOnBorderField(QWidget):
    """Pill with white border; label on the top edge, left of center (fieldset-legend)."""

    def __init__(self, text: str, inner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._inner = inner
        m_l, _m_t, _m_r, _m_b = _PILL_INNER_M
        self._label_x = m_l + 2
        self._label = QLabel(text)
        self._label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label.setStyleSheet(
            f"QLabel {{ background-color: {_IDLE_PILL_BG}; color: rgba(255, 255, 255, 0.9); "
            f"font-size: 11px; font-weight: 500; padding: 0 {_PILL_LABEL_PAD_H}px; }}"
        )
        self._box = QFrame()
        self._box.setObjectName("idlePill")
        self._box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._box.setStyleSheet(
            f"""
            QFrame#idlePill {{
                background: {_IDLE_PILL_BG};
                border: 1px solid rgba(255, 255, 255, 0.92);
                border-radius: 22px;
            }}
            """
        )
        lay = QVBoxLayout(self._box)
        lay.setContentsMargins(*_PILL_INNER_M)
        lay.setSpacing(0)
        lay.addWidget(inner, 0, Qt.AlignmentFlag.AlignLeft)
        self._box.setParent(self)
        self._label.setParent(self)
        self._label.raise_()
        self.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )

    def minimumSizeHint(self) -> QSize:
        lh = max(1, self._label.sizeHint().height())
        y_split = (lh + 1) // 2
        m_l, m_t, m_r, m_b = _PILL_INNER_M
        in_sh = self._inner.sizeHint()
        in_w, in_h = in_sh.width(), in_sh.height()
        if self._inner.minimumWidth() > 0:
            in_w = max(in_w, self._inner.minimumWidth())
        if self._inner.minimumHeight() > 0:
            in_h = max(in_h, self._inner.minimumHeight())
        box_w = m_l + m_r + in_w
        box_h = m_t + m_b + in_h
        lw = self._label.sizeHint().width()
        w = max(box_w, self._label_x + lw + 4)
        h = y_split + box_h
        return QSize(w, h)

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        h_label = self._label.sizeHint().height()
        y_split = (h_label + 1) // 2
        label_w = self._label.sizeHint().width()
        x = min(self._label_x, max(0, w - label_w))
        self._label.setGeometry(x, 0, label_w, h_label)
        self._box.setGeometry(0, y_split, w, max(0, h - y_split))


class MainWindow(QMainWindow):
    """Сигналы из фоновых потоков → GUI-поток."""
    _signal_client_disconnected = Signal()
    _signal_webrtc_disconnected = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        ip = _desktop_icon_path()
        if ip is not None:
            self.setWindowIcon(QIcon(str(ip)))
        self.setMinimumSize(880, 480)
        self.resize(1080, 600)

        self._frame_store = FrameStore()
        self._preview_rgb_lock = threading.Lock()
        self._preview_rgb: object | None = None
        self._preview_rgb_epoch = 0
        self._server: StreamServer | None = None
        self._webrtc_mgr: object | None = None
        self._webrtc_signaling: object | None = None
        self._webrtc_signaling_port = DEFAULT_WEBRTC_SIGNALING_PORT
        # WebRTC = hardware H.264/VP8 path (aiortc <-> flutter_webrtc / MediaCodec).
        # Включён по умолчанию: pure-Dart JPEG энкодер на телефоне ограничивает
        # TCP/JPEG путь до 5..12 fps с большой задержкой, что и было основной
        # причиной лагов в горизонтальной сборке. WebRTC даёт 30 fps и низкую
        # латентность за счёт аппаратного кодирования и адаптивного битрейта.
        # Принудительно отключить можно через SMART_CAM_DISABLE_WEBRTC=1.
        self._enable_webrtc = (
            WebRtcSessionManager is not None and WebRtcSignalingServer is not None
        )
        force_disable = (
            str(os.environ.get("SMART_CAM_DISABLE_WEBRTC", "0")).strip().lower()
            in ("1", "true", "yes")
        )
        # Старый флаг ENABLE остаётся как явное ВКЛ для отладки, но больше не нужен
        # для активации WebRTC — он включён сам.
        legacy_force_enable = (
            str(os.environ.get("SMART_CAM_ENABLE_WEBRTC", "")).strip().lower()
            in ("1", "true", "yes")
        )
        if force_disable and not legacy_force_enable:
            self._enable_webrtc = False
        if self._enable_webrtc and (
            WebRtcSessionManager is None or WebRtcSignalingServer is None
        ):
            self._enable_webrtc = False
            logger.warning("WebRTC disabled: optional dependencies are unavailable")
        self._vcam: VCamWorker | None = None
        self._ndi: NdiWorker | None = None
        self._output_mode = str(
            os.environ.get("SMART_CAM_OUTPUT_MODE", "virtualcam")
        ).strip().lower()
        self._preview_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._last_preview_jpeg: bytes | None = None
        self._last_start_cable = False
        self._listen_bootstrapped = False
        self._listen_was_cable = False
        self._preview_epoch = 0
        self._syncing_seg = False
        self._discovery_server: DiscoveryServer | None = None
        self._zeroconf: object | None = None
        self._zeroconf_info: object | None = None
        self._syncing_idle_host = False
        self._syncing_idle_port = False
        self._syncing_idle_token = False

        self._app_settings = QSettings("SmartCam", "SmartCamDesktop")
        self._initial_cable_mode = self._load_initial_cable_mode()

        self._signal_client_disconnected.connect(self._on_phone_tcp_closed)
        self._signal_webrtc_disconnected.connect(self._on_webrtc_closed)

        # Центр: стек; служебные поля сервера — в скрытом виджете (синхрон с верхом).
        shell = QWidget()
        self.setCentralWidget(shell)

        # Main preview / QR stack
        self._stack = QStackedWidget()

        self._brand_idle = _BrandIdlePanel()
        self._idle_page = QWidget()
        pw = QVBoxLayout(self._idle_page)
        pw.setContentsMargins(0, 0, 0, 0)
        pw.setSpacing(0)
        pw.addWidget(self._brand_idle, stretch=1)
        self._idle_top: QWidget | None = None
        page_wait = self._idle_page
        self._qr_main = QLabel()
        self._qr_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_main.setFixedSize(QR_MAIN_PX + 24, QR_MAIN_PX + 24)
        self._qr_main.setScaledContents(False)
        self._qr_main.setStyleSheet("background: white; border-radius: 16px; padding: 12px;")
        self._qr_meta_main = QLabel()
        self._qr_meta_main.setObjectName("hint")
        self._qr_meta_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_meta_main.setWordWrap(True)

        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_label.setStyleSheet("background: #1a1a1a; border-radius: 12px;")
        self._video_label.setScaledContents(False)

        self._stack.addWidget(page_wait)
        self._stack.addWidget(self._video_label)

        self._center = _MainStage(self._stack, shell)

        self._hidden = QWidget(shell)
        self._hidden.setVisible(False)
        self._seg = _SegmentSwitch(
            self._on_mode_changed,
            initial_cable=self._initial_cable_mode,
            parent=self._hidden,
        )
        self._host_edit = QLineEdit("0.0.0.0", self._hidden)
        self._host_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._port_spin = QSpinBox(self._hidden)
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(DEFAULT_PORT)
        self._port_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._token_edit = QLineEdit(self._hidden)
        self._token_edit.setMaxLength(_K_TOKEN_MAX_CHARS)
        self._token_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        regen_icon = QIcon.fromTheme(
            "view-refresh",
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        )
        self._regen_btn = _TokenRegenButton(
            regen_icon,
            36,
            self._regen_token,
            self._hidden,
            object_name="tokenRegen",
            tool_tip="Сгенерировать токен",
        )
        tr = QHBoxLayout()
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(4)
        tr.addWidget(self._token_edit, stretch=1)
        tr.addWidget(self._regen_btn, 0, Qt.AlignmentFlag.AlignCenter)
        tw = QWidget(self._hidden)
        tw.setLayout(tr)
        tw.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        _hv = QVBoxLayout(self._hidden)
        _hv.setContentsMargins(0, 0, 0, 0)
        _hv.setSpacing(6)
        _hv.addWidget(self._seg)
        _hv.addWidget(self._host_edit)
        _hv.addWidget(self._port_spin)
        _hv.addWidget(tw)

        self._idle_top = self._build_idle_top_strip()
        self._idle_top.setParent(shell)
        self._idle_top.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self._idle_top.setAutoFillBackground(False)
        self._idle_top_peek = self._build_idle_top_peek_strip()
        self._idle_top_peek.setParent(shell)
        self._idle_top_peek.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self._idle_top_peek.setAutoFillBackground(False)
        self._idle_top_anim: QPropertyAnimation | None = None
        self._idle_top_revealed: bool = False
        self._center_qr_cached = QPixmap()
        # Для отслеживания «курсор в окне» используем дешёвый поллинг —
        # надёжнее чем enter/leaveEvent, которые срабатывают при переходе
        # мыши между родителем и его детьми.
        self._hover_poll = QTimer(self)
        self._hover_poll.setInterval(80)
        self._hover_poll.timeout.connect(self._poll_window_hover)
        QTimer.singleShot(0, self, self._initialize_idle_top_hidden)

        for w in [shell, *shell.findChildren(QWidget)]:
            w.setMouseTracking(True)
            w.installEventFilter(self)

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(33)
        self._preview_timer.timeout.connect(self._tick_preview)

        self._connecting_dot_phases = [".", "..", "...", ".."]
        self._connecting_dot_idx = 0
        self._connecting_dots_timer = QTimer(self)
        self._connecting_dots_timer.setInterval(320)
        self._connecting_dots_timer.timeout.connect(self._tick_connecting_dots)
        self._connecting_dots_timer.start()

        self._ip_timer = QTimer(self)
        self._ip_timer.timeout.connect(self._update_qr)
        self._ip_timer.start(4000)

        self._host_edit.textChanged.connect(lambda _: self._update_qr())
        self._port_spin.valueChanged.connect(lambda _: self._update_qr())
        self._token_edit.textChanged.connect(self._on_token_field_changed)

        if not self._token_edit.text().strip():
            self._regen_token()
        else:
            self._update_qr()
        self._stack.setCurrentIndex(0)
        self._apply_qr_visibility()
        QTimer.singleShot(0, self, self._apply_main_layout_geometry)
        self._bootstrap_listen_server()

    def _on_top_connection_seg(self, cable: bool) -> None:
        if self._syncing_seg:
            return
        self._syncing_seg = True
        self._seg.set_cable(cable)
        self._syncing_seg = False
        self._on_mode_changed(cable)

    def _build_idle_top_peek_strip(self) -> QWidget:
        out = QFrame()
        out.setObjectName("idleTopPeek")
        out.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        out.setStyleSheet("QFrame#idleTopPeek { background: transparent; border: none; }")
        self._peek_status = QLabel("Подключение")
        self._peek_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._peek_status.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 600;",
        )
        self._peek_status_dots = QLabel("...")
        self._peek_status_dots.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._peek_status_dots.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 600;",
        )
        _peek_fm = QFontMetrics(self._peek_status_dots.font())
        self._peek_status_dots.setFixedWidth(_peek_fm.horizontalAdvance("...") + 2)
        peek_row = QWidget()
        peek_row_l = QHBoxLayout(peek_row)
        peek_row_l.setContentsMargins(0, 0, 0, 0)
        peek_row_l.setSpacing(0)
        peek_row_l.addStretch(1)
        peek_row_l.addWidget(self._peek_status)
        peek_row_l.addWidget(self._peek_status_dots)
        peek_row_l.addStretch(1)
        ch = QLabel()
        ch.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ch_path = _down2_chevron_path()
        if ch_path is not None:
            ch_pm = QIcon(str(ch_path)).pixmap(QSize(18, 18))
            if not ch_pm.isNull():
                ch.setPixmap(ch_pm)
            else:
                ch.setText("⌄")
                ch.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 300;")
        else:
            ch.setText("⌄")
            ch.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 300;")
        v = QVBoxLayout(out)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(0)
        v.addWidget(peek_row)
        v.addWidget(ch)
        return out

    def _tick_connecting_dots(self) -> None:
        if not hasattr(self, "_idle_status_dots") or self._idle_status_dots is None:
            return
        phase = self._connecting_dot_phases[self._connecting_dot_idx]
        self._connecting_dot_idx = (self._connecting_dot_idx + 1) % len(self._connecting_dot_phases)
        self._idle_status_dots.setText(phase)
        if hasattr(self, "_peek_status_dots") and self._peek_status_dots is not None:
            self._peek_status_dots.setText(phase)

    def _bind_dup_lineedits(self, a: QLineEdit, b: QLineEdit) -> None:
        def push_a_to_b(_: str) -> None:
            if self._syncing_idle_host:
                return
            self._syncing_idle_host = True
            b.setText(a.text())
            self._syncing_idle_host = False

        def push_b_to_a(_: str) -> None:
            if self._syncing_idle_host:
                return
            self._syncing_idle_host = True
            a.setText(b.text())
            self._syncing_idle_host = False

        a.textChanged.connect(push_a_to_b)
        b.textChanged.connect(push_b_to_a)
        self._syncing_idle_host = True
        b.setText(a.text())
        self._syncing_idle_host = False

    def _bind_dup_token_lineedits(self, a: QLineEdit, b: QLineEdit) -> None:
        def push_a_to_b(_: str) -> None:
            if self._syncing_idle_token:
                return
            self._syncing_idle_token = True
            b.setText(a.text())
            self._syncing_idle_token = False

        def push_b_to_a(_: str) -> None:
            if self._syncing_idle_token:
                return
            self._syncing_idle_token = True
            a.setText(b.text())
            self._syncing_idle_token = False

        a.textChanged.connect(push_a_to_b)
        b.textChanged.connect(push_b_to_a)
        self._syncing_idle_token = True
        b.setText(a.text())
        self._syncing_idle_token = False

    def _bind_dup_spin(self, a: QSpinBox, b: QSpinBox) -> None:
        def push_a_to_b(v: int) -> None:
            if self._syncing_idle_port:
                return
            self._syncing_idle_port = True
            b.setValue(v)
            self._syncing_idle_port = False

        def push_b_to_a(v: int) -> None:
            if self._syncing_idle_port:
                return
            self._syncing_idle_port = True
            a.setValue(v)
            self._syncing_idle_port = False

        a.valueChanged.connect(push_a_to_b)
        b.valueChanged.connect(push_b_to_a)
        self._syncing_idle_port = True
        b.setValue(a.value())
        self._syncing_idle_port = False

    def _build_idle_top_strip(self) -> QWidget:
        field_css = (
            "QLineEdit, QSpinBox { color: #ffffff; font-size: 12px; background: transparent; border: none; }"
        )
        self._host_top = QLineEdit()
        self._host_top.setStyleSheet(field_css)
        self._host_top.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
        )
        self._port_top = QSpinBox()
        self._port_top.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._port_top.setRange(1024, 65535)
        self._port_top.setStyleSheet(field_css)
        self._port_top.setValue(self._port_spin.value())
        self._port_top.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
        )
        self._token_top = QLineEdit()
        self._token_top.setStyleSheet(field_css)
        self._token_top.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
        )
        _fm = QFontMetrics(self._host_top.font())
        _w_field = _lineedit_w_for_chars(_fm, _K_IDLE_FIELD_UNIFORM_CHARS, 14)
        self._host_top.setMaxLength(45)
        self._host_top.setFixedWidth(_w_field)
        self._port_top.setFixedWidth(_w_field)
        self._token_top.setMaxLength(_K_TOKEN_MAX_CHARS)
        self._token_top.setFixedWidth(_w_field)
        self._host_top.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._port_top.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._token_top.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        # QSpinBox is often taller than QLineEdit; unify row height
        _h_field = self._host_top.sizeHint().height()
        for _w in (self._host_top, self._port_top, self._token_top):
            _w.setFixedHeight(_h_field)
        regen_icon2 = QIcon.fromTheme(
            "view-refresh",
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        )
        self._regen_btn_top = _TokenRegenButton(
            regen_icon2,
            32,
            self._regen_token,
            None,
            object_name="tokenRegenTop",
            tool_tip="Сгенерировать новый токен",
        )

        self._bind_dup_lineedits(self._host_edit, self._host_top)
        self._bind_dup_spin(self._port_spin, self._port_top)
        self._bind_dup_token_lineedits(self._token_edit, self._token_top)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)
        row1.addWidget(_PillOnBorderField("Хост", self._host_top))
        row1.addWidget(_PillOnBorderField("Порт", self._port_top))
        tw = QHBoxLayout()
        tw.setContentsMargins(0, 0, 0, 0)
        tw.setSpacing(2)
        tw.addWidget(self._token_top, 0, Qt.AlignmentFlag.AlignLeft)
        tw.addWidget(self._regen_btn_top, 0, Qt.AlignmentFlag.AlignRight)
        tw_widget = QWidget()
        tw_widget.setLayout(tw)
        tw_widget.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed,
        )
        row1.addWidget(_PillOnBorderField("Токен", tw_widget))

        self._seg_top = _SegmentSwitch(
            self._on_top_connection_seg,
            initial_cable=self._seg.is_cable(),
            cable_label="По кабелю",
            wifi_label="По WI-FI",
        )
        self._seg_top.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed,
        )
        self._seg_top.setStyleSheet(
            """
            QFrame#segShell {
                background: #002EE8;
                border: 1px solid #ffffff;
                border-radius: 22px;
            }
            QPushButton#segBtnLeft,
            QPushButton#segBtnRight {
                font-weight: 600;
                font-size: 13px;
                border: none;
                padding: 10px 20px;
                min-height: 22px;
                min-width: 120px;
            }
            QPushButton#segBtnLeft:checked {
                background: #ffffff;
                color: #002EE8;
                border-radius: 18px;
            }
            QPushButton#segBtnLeft:!checked {
                background: #002EE8;
                color: #ffffff;
                border-radius: 18px;
            }
            QPushButton#segBtnRight:checked {
                background: #ffffff;
                color: #002EE8;
                border-radius: 18px;
            }
            QPushButton#segBtnRight:!checked {
                background: #002EE8;
                color: #ffffff;
                border-radius: 18px;
            }
            """
        )

        self._idle_hint = QLabel("Если не удается подключится,\nотсканируйте QR в приложении")
        self._idle_hint.setWordWrap(True)
        self._idle_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._idle_hint.setStyleSheet(
            "color: rgba(255, 255, 255, 0.55); font-size: 11px; font-weight: 500;",
        )
        self._idle_status = QLabel("Подключение")
        self._idle_status.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 600;",
        )
        self._idle_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._idle_status_dots = QLabel("...")
        self._idle_status_dots.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 600;",
        )
        self._idle_status_dots.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        _idle_fm = QFontMetrics(self._idle_status_dots.font())
        self._idle_status_dots.setFixedWidth(_idle_fm.horizontalAdvance("...") + 2)
        idle_status_row = QWidget()
        idle_status_row_l = QHBoxLayout(idle_status_row)
        idle_status_row_l.setContentsMargins(0, 0, 0, 0)
        idle_status_row_l.setSpacing(0)
        idle_status_row_l.addStretch(1)
        idle_status_row_l.addWidget(self._idle_status)
        idle_status_row_l.addWidget(self._idle_status_dots)
        idle_status_row_l.addStretch(1)
        self._idle_info = QLabel("")
        self._idle_info.setWordWrap(True)
        self._idle_info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._idle_info.setStyleSheet(
            "color: rgba(255, 255, 255, 0.58); font-size: 10px; font-weight: 500;",
        )
        self._idle_info.setVisible(False)
        ch = QLabel()
        ch.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ch_path = _down2_chevron_path()
        if ch_path is not None:
            # down2.svg from project root (or fallback "Arrow - Down 2.svg")
            # to match the design glyph exactly.
            ch_pm = QIcon(str(ch_path)).pixmap(QSize(18, 18))
            if not ch_pm.isNull():
                ch.setPixmap(ch_pm)
            else:
                ch.setText("⌄")
                ch.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 300;")
        else:
            ch.setText("⌄")
            ch.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 300;")
        v3 = QVBoxLayout()
        v3.setContentsMargins(0, 0, 0, 0)
        v3.setSpacing(0)
        v3.addWidget(self._idle_hint)
        v3.addSpacing(3)
        v3.addWidget(idle_status_row)
        v3.addWidget(self._idle_info)
        v3.addWidget(ch)
        v3w = QWidget()
        v3w.setLayout(v3)

        r1w = QWidget()
        r1w.setLayout(row1)
        r1w.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        r1w_wrap = QWidget()
        r1w_wrap_l = QHBoxLayout(r1w_wrap)
        r1w_wrap_l.setContentsMargins(0, 0, 0, 0)
        r1w_wrap_l.addStretch(1)
        r1w_wrap_l.addWidget(r1w, 0, Qt.AlignmentFlag.AlignHCenter)
        r1w_wrap_l.addStretch(1)

        self._qr_settings = QLabel()
        self._qr_settings.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_settings.setMinimumSize(160, 160)
        self._qr_settings.setMaximumSize(200, 200)
        self._qr_settings.setStyleSheet(
            "background: transparent; border: none; padding: 4px;",
        )
        self._qr_settings.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self._qr_settings.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
        )
        # QR теперь показывается в центре колец (на месте логотипа).
        # Дубликат в верхней панели не нужен.
        self._qr_settings.setVisible(False)
        self._qr_meta_set = QLabel()
        self._qr_meta_set.setObjectName("qrMeta")
        self._qr_meta_set.setWordWrap(True)
        self._qr_meta_set.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._qr_meta_set.setStyleSheet(
            "color: rgba(255, 255, 255, 0.65); font-size: 10px; font-weight: 500;",
        )
        self._qr_meta_set.setVisible(False)

        out = QFrame()
        out.setObjectName("idleTopStrip")
        out.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        out.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        out.setAutoFillBackground(False)
        out.setStyleSheet("QFrame#idleTopStrip { background: transparent; border: none; }")
        o = QVBoxLayout(out)
        o.setContentsMargins(24, 10, 24, 8)
        o.setSpacing(10)
        o.addWidget(r1w_wrap)
        o.addWidget(self._seg_top, 0, Qt.AlignmentFlag.AlignHCenter)
        o.addWidget(v3w, 0, Qt.AlignmentFlag.AlignHCenter)
        o.addWidget(self._qr_settings, 0, Qt.AlignmentFlag.AlignHCenter)
        o.addWidget(self._qr_meta_set, 0, Qt.AlignmentFlag.AlignHCenter)
        out.setMaximumWidth(920)
        out.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        return out

    def _position_idle_top_overlay(self) -> None:
        if self._idle_top is None:
            return
        shell = self.centralWidget()
        if shell is None or shell.width() <= 0:
            return
        w = shell.width()
        if hasattr(self, "_idle_top_peek") and self._idle_top_peek is not None:
            self._idle_top_peek.setFixedWidth(w)
            self._idle_top_peek.adjustSize()
            ph = max(1, self._idle_top_peek.sizeHint().height())
            self._idle_top_peek.setGeometry(0, 0, w, ph)
        self._idle_top.setFixedWidth(w)
        self._idle_top.adjustSize()
        h = self._idle_top.sizeHint().height()
        if h < 1:
            h = max(1, self._idle_top.height())
        # Геометрия фиксирует целевую Y (0 если раскрыта, -h если спрятана);
        # анимация двигает только во время переходов.
        target_y = 0 if self._idle_top_revealed else -h
        running_anim = (
            self._idle_top_anim is not None
            and self._idle_top_anim.state() == QAbstractAnimation.State.Running
        )
        cur_y = self._idle_top.y() if running_anim else target_y
        self._idle_top.setGeometry(0, cur_y, w, h)
        self._idle_top.raise_()

    def _initialize_idle_top_hidden(self) -> None:
        """Стартовое позиционирование: вся панель спрятана сверху."""
        if self._idle_top is None:
            return
        shell = self.centralWidget()
        if shell is None:
            return
        w = max(1, shell.width())
        self._idle_top.setFixedWidth(w)
        self._idle_top.adjustSize()
        h = max(1, self._idle_top.sizeHint().height())
        self._idle_top_revealed = False
        self._idle_top.setGeometry(0, -h, w, h)
        self._idle_top.show()
        if hasattr(self, "_idle_top_peek") and self._idle_top_peek is not None:
            self._idle_top_peek.show()
        self._position_idle_top_overlay()
        self._idle_top.raise_()
        self._hover_poll.start()
        # Если курсор уже над окном, сразу раскрываем без задержки.
        if self._cursor_inside_window() and self._idle_top_visible_by_state():
            self._set_idle_top_revealed(True, animate=False)

    def _idle_top_visible_by_state(self) -> bool:
        """Можно ли вообще показывать панель (idle-страница и окно видимо)."""
        if not self.isVisible():
            return False
        if self.isMinimized():
            return False
        if self._stack.currentIndex() != 0:
            return False
        return True

    def _cursor_inside_window(self) -> bool:
        return self.frameGeometry().contains(QCursor.pos())

    def _poll_window_hover(self) -> None:
        if self._idle_top is None:
            return
        if not self._idle_top_visible_by_state():
            if self._idle_top_revealed:
                self._set_idle_top_revealed(False)
            return
        want = self._cursor_inside_window()
        if want != self._idle_top_revealed:
            self._set_idle_top_revealed(want)

    def _sync_idle_center_with_overlay_state(self) -> None:
        """Единый источник правды: открыт попап -> QR, закрыт -> логотип."""
        if self._center_qr_cached.isNull():
            self._brand_idle.set_center_qr(None)
            self._brand_idle.set_center_qr_visible(False)
            return
        self._brand_idle.set_center_qr(self._center_qr_cached)
        self._brand_idle.set_center_qr_visible(self._idle_top_revealed)

    def _set_idle_top_revealed(self, on: bool, *, animate: bool = True) -> None:
        if self._idle_top is None:
            return
        shell = self.centralWidget()
        if shell is None:
            return
        # В live-режиме панель и peek скрыты целиком (см. _apply_qr_visibility).
        if on and self._stack.currentIndex() != 0:
            on = False
        if self._idle_top_anim is not None:
            self._idle_top_anim.stop()
            self._idle_top_anim = None
        self._idle_top_revealed = on
        if hasattr(self, "_idle_top_peek") and self._idle_top_peek is not None:
            self._idle_top_peek.setVisible(not on)
        # Синхронизируем визуал центра и оффсет теней колец строго с открытием попапа.
        self._brand_idle.set_ring_hover_target(1.0 if on else 0.0)
        self._sync_idle_center_with_overlay_state()
        w = max(1, shell.width())
        self._idle_top.setFixedWidth(w)
        self._idle_top.adjustSize()
        h = max(1, self._idle_top.sizeHint().height())
        target_y = 0 if on else -h
        cur_y = self._idle_top.y()
        self._idle_top.show()
        self._idle_top.raise_()
        if not animate or cur_y == target_y:
            self._idle_top.move(0, target_y)
            return
        anim = QPropertyAnimation(self._idle_top, b"pos", self)
        anim.setDuration(360)
        anim.setEasingCurve(
            QEasingCurve.Type.OutCubic if on else QEasingCurve.Type.InCubic,
        )
        anim.setStartValue(QPoint(0, cur_y))
        anim.setEndValue(QPoint(0, target_y))
        anim.start()
        self._idle_top_anim = anim

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        apply_windows_caption_brand(self)

    def _bootstrap_listen_server(self) -> None:
        if self._listen_bootstrapped:
            return
        self._listen_bootstrapped = True
        token = self._token_edit.text().strip()
        if not token:
            self._regen_token()
            token = self._token_edit.text().strip()
        host = self._host_edit.text().strip() or "0.0.0.0"
        port = self._port_spin.value()
        self._webrtc_signaling_port = max(1024, min(65535, port + 1))
        self._listen_was_cable = self._seg.is_cable()
        if self._listen_was_cable:
            ok, adb_msg = adb_reverse_tcp(port)
            if ok:
                self._append_status(f"USB: adb reverse tcp:{port} (OK)")
            else:
                self._append_status(f"USB: adb reverse not set — {adb_msg}")
            ok_disc, adb_disc_msg = adb_reverse_tcp(DEFAULT_DISCOVERY_PORT)
            if ok_disc:
                self._append_status(f"USB: adb reverse tcp:{DEFAULT_DISCOVERY_PORT} discovery (OK)")
            else:
                self._append_status(f"USB: adb reverse discovery not set — {adb_disc_msg}")
            if self._enable_webrtc:
                ok_sig, adb_sig_msg = adb_reverse_tcp(self._webrtc_signaling_port)
                if ok_sig:
                    self._append_status(
                        f"USB: adb reverse tcp:{self._webrtc_signaling_port} signaling (OK)"
                    )
                else:
                    self._append_status(
                        f"USB: adb reverse signaling not set — {adb_sig_msg}"
                    )

        self._server = StreamServer(
            host,
            port,
            token,
            self._frame_store,
            on_state=self._on_state,
            on_jpeg_frame=self._jpeg_from_server,
            on_phone_session=self._phone_session_bridge,
            on_client_disconnect=self._notify_tcp_client_disconnected,
        )
        self._server.start()

        # USB discovery: phone hits GET http://127.0.0.1:17776/info via ADB reverse.
        _pc_name = self._get_pc_name()
        _disc_sp = self._webrtc_signaling_port if self._enable_webrtc else None
        _disc_mode = "webrtc" if self._enable_webrtc else None
        self._discovery_server = DiscoveryServer(
            DEFAULT_DISCOVERY_PORT,
            port,
            token,
            name=_pc_name,
            signaling_port=_disc_sp,
            mode=_disc_mode,
            lan_ip=default_lan_ip(),
        )
        self._discovery_server.start()

        # WiFi discovery: broadcast via mDNS so the phone finds us on the LAN.
        self._start_mdns(
            port,
            token,
            name=_pc_name,
            signaling_port=_disc_sp,
            mode=_disc_mode,
        )

        if self._enable_webrtc:
            if WebRtcSessionManager is None or WebRtcSignalingServer is None:
                self._append_status("WebRTC disabled: aiortc/aiohttp not available")
                self._enable_webrtc = False
            else:
                self._webrtc_mgr = WebRtcSessionManager(
                    self._frame_store,
                    on_state=self._on_state,
                    on_rgb_frame=self._webrtc_rgb_to_preview,
                )
                self._webrtc_signaling = WebRtcSignalingServer(
                    host,
                    self._webrtc_signaling_port,
                    token,
                    self._webrtc_mgr,
                    on_state=self._on_state,
                )
                self._webrtc_signaling.start()
        # Сервер уже слушает на 0.0.0.0, поэтому поле можно оставить активным как
        # ручной override адреса в QR (например "реальный Wi‑Fi IP" вместо авто-выбора).
        self._host_edit.setEnabled(True)
        self._port_spin.setEnabled(False)
        self._token_edit.setEnabled(True)
        # Bind/port фиксированы после старта слушателя; токен, Cable/Wi‑Fi и ↻ — можно менять.

        self._server.set_pc_session_live(True)
        vcam_w = int(os.environ.get("SMART_CAM_VCAM_WIDTH", "1280"))
        vcam_h = int(os.environ.get("SMART_CAM_VCAM_HEIGHT", "720"))
        vcam_fps = int(os.environ.get("SMART_CAM_VCAM_FPS", "30"))
        if self._output_mode in ("virtualcam", "both", ""):
            self._vcam = VCamWorker(
                self._frame_store,
                on_state=self._on_state,
                fps=vcam_fps,
                width=vcam_w,
                height=vcam_h,
            )
            self._vcam.start()
        if self._output_mode in ("ndi", "both"):
            self._ndi = NdiWorker(self._frame_store, on_state=self._on_state)
            self._ndi.start()
        self._preview_timer.start()

    @staticmethod
    def _get_pc_name() -> str:
        """Short hostname of this PC sent to the phone as the display name."""
        try:
            return socket.gethostname() or ""
        except OSError:
            return ""

    def _start_mdns(
        self,
        port: int,
        token: str,
        name: str = "",
        signaling_port: int | None = None,
        mode: str | None = None,
    ) -> None:
        """Register mDNS service so phone discovers PC on the WiFi network."""
        if not _ZEROCONF_AVAILABLE:
            logger.warning(
                "zeroconf not available — Wi-Fi auto-discovery disabled. "
                "Run `pip install zeroconf` to enable phone-finds-PC over LAN."
            )
            self._append_status(
                "WiFi: автообнаружение выключено (нет zeroconf — установите: pip install zeroconf)"
            )
            return
        lan_ip = default_lan_ip()
        try:
            import socket as _sock
            from zeroconf import ServiceInfo, Zeroconf  # type: ignore[import]
            props: dict = {"t": token}
            if name:
                props["n"] = name
            if signaling_port is not None:
                props["sp"] = str(int(signaling_port))
            if mode:
                props["m"] = mode
            info = ServiceInfo(
                "_smartcam._tcp.local.",
                "SmartCam._smartcam._tcp.local.",
                addresses=[_sock.inet_aton(lan_ip)],
                port=port,
                properties=props,
            )
            zc = Zeroconf()
            zc.register_service(info)
            self._zeroconf = zc
            self._zeroconf_info = info
            logger.info("mDNS registered: SmartCam on %s:%s", lan_ip, port)
        except Exception as exc:
            logger.warning("mDNS registration failed: %s", exc)

    def _stop_mdns(self) -> None:
        zc = self._zeroconf
        info = self._zeroconf_info
        self._zeroconf = None
        self._zeroconf_info = None
        if zc is not None and info is not None:
            try:
                from zeroconf import Zeroconf  # type: ignore[import]
                assert isinstance(zc, Zeroconf)
                zc.unregister_service(info)  # type: ignore[arg-type]
                zc.close()
            except Exception:
                pass

    def _on_token_field_changed(self) -> None:
        self._update_qr()
        if self._server is None:
            return
        t = self._token_edit.text().strip()
        if t:
            self._server.set_token(t)
            if self._discovery_server is not None:
                self._discovery_server.set_token(t)
            if self._enable_webrtc and self._webrtc_signaling is not None:
                self._webrtc_signaling.set_token(t)

    def _phone_session_bridge(self, want: bool) -> None:
        QTimer.singleShot(0, self, lambda w=want: self._apply_phone_session(w))

    def _notify_tcp_client_disconnected(self) -> None:
        self._signal_client_disconnected.emit()

    def _on_phone_tcp_closed(self) -> None:
        self._preview_epoch += 1
        with self._preview_rgb_lock:
            self._preview_rgb = None
        with self._preview_lock:
            self._latest_jpeg = None
        self._last_preview_jpeg = None
        self._video_label.clear()
        self._video_label.update()
        self._stack.setCurrentIndex(0)
        self._apply_qr_visibility()

    def _on_webrtc_closed(self) -> None:
        """Вызывается (через Signal) когда WebRTC-соединение с телефоном закрылось."""
        self._preview_epoch += 1
        with self._preview_rgb_lock:
            self._preview_rgb = None
        with self._preview_lock:
            self._latest_jpeg = None
        self._last_preview_jpeg = None
        self._video_label.clear()
        self._video_label.update()
        self._stack.setCurrentIndex(0)
        self._apply_qr_visibility()

    def _apply_phone_session(self, _want: bool) -> None:
        """Сессия на ПК всегда активна; Start/Stop с телефона не используются."""

    def _apply_main_layout_geometry(self) -> None:
        shell = self.centralWidget()
        if shell is None:
            return
        w, h = shell.width(), shell.height()
        if w <= 0 or h <= 0:
            return
        self._center.setGeometry(0, 0, w, h)
        self._position_idle_top_overlay()
        if self._idle_top is not None:
            self._idle_top.raise_()

    def _on_mode_changed(self, cable: bool) -> None:
        if not self._syncing_seg:
            if hasattr(self, "_seg_top") and self._seg_top is not None:
                self._syncing_seg = True
                self._seg_top.set_cable(cable)
                self._syncing_seg = False
        port = self._port_spin.value()
        signaling_port = self._webrtc_signaling_port
        if cable:
            ok, adb_msg = adb_reverse_tcp(port)
            if ok:
                self._append_status(f"USB: adb reverse tcp:{port} (OK)")
            else:
                self._append_status(f"USB: adb reverse not set — {adb_msg}")
            if self._enable_webrtc:
                ok_sig, adb_sig_msg = adb_reverse_tcp(signaling_port)
                if ok_sig:
                    self._append_status(
                        f"USB: adb reverse tcp:{signaling_port} signaling (OK)"
                    )
                else:
                    self._append_status(
                        f"USB: adb reverse signaling not set — {adb_sig_msg}"
                    )
        else:
            adb_reverse_remove(port)
            if self._enable_webrtc:
                adb_reverse_remove(signaling_port)
            self._append_status("USB: adb reverse removed (Wi‑Fi mode)")
        self._listen_was_cable = cable
        self._save_cable_mode(cable)
        self._update_qr()

    def _qr_host_for_phone(self) -> str:
        if self._seg.is_cable():
            return "127.0.0.1"
        h = self._host_edit.text().strip()
        if h.lower() in ("", "0.0.0.0", "::", "127.0.0.1", "::1", "localhost"):
            return default_lan_ip()
        return h

    def _load_initial_cable_mode(self) -> bool:
        """
        Persisted default: Wi-Fi (False).
        Cable remains available but should be explicitly selected.
        """
        raw = self._app_settings.value("connection/mode", "wifi")
        if isinstance(raw, str):
            return raw.strip().lower() == "cable"
        return bool(raw)

    def _save_cable_mode(self, cable: bool) -> None:
        self._app_settings.setValue("connection/mode", "cable" if cable else "wifi")

    def _pointer_over_idle_hero(self) -> bool:
        if self._stack.currentIndex() != 0:
            return False
        w = QApplication.widgetAt(QCursor.pos())
        if w is None:
            return False
        if w is self._idle_page or self._idle_page.isAncestorOf(w):
            return True
        it = self._idle_top
        if it is not None and (w is it or it.isAncestorOf(w)):
            return True
        return False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        # Кольца и центр синхронизируются с состоянием попапа в `_set_idle_top_revealed`,
        # чтобы не было рассинхрона из-за пропущенных/лишних MouseMove-событий.
        return False

    def _jpeg_from_server(self, frame: object) -> None:
        """Вызывается из потока StreamServer — обновление UI только в GUI-потоке Qt."""
        try:
            import numpy as _np
        except Exception:
            return
        if isinstance(frame, _np.ndarray):
            self._webrtc_rgb_to_preview(frame)
            return
        ep = self._preview_epoch
        with self._preview_lock:
            self._latest_jpeg = bytes(frame)
        QTimer.singleShot(0, self, lambda: self._tick_preview_deferred(ep))

    def _webrtc_rgb_to_preview(self, rgb) -> None:  # type: ignore[no-untyped-def]
        """Store downscaled RGB for UI preview — no JPEG re-encode on the hot path."""
        import time as _time

        now = _time.monotonic()
        last = getattr(self, "_last_webrtc_preview_t", 0.0)
        if now - last < 0.066:  # ~15 fps preview cap
            return
        self._last_webrtc_preview_t = now  # type: ignore[attr-defined]

        try:
            import numpy as _np
            from PIL import Image as _PILImage
        except Exception:
            return
        try:
            arr = rgb
            if not isinstance(arr, _np.ndarray) or arr.ndim != 3 or arr.shape[2] != 3:
                return
            h, w = arr.shape[:2]
            target_long = 960
            long_side = max(w, h)
            if long_side > target_long:
                scale = target_long / float(long_side)
                new_w = max(2, int(w * scale))
                new_h = max(2, int(h * scale))
                pil = _PILImage.fromarray(arr, mode="RGB").resize(
                    (new_w, new_h), _PILImage.Resampling.LANCZOS
                )
                small = _np.asarray(pil, dtype=_np.uint8)
            else:
                small = arr if arr.flags["C_CONTIGUOUS"] else _np.ascontiguousarray(arr)
            ep = self._preview_epoch
            with self._preview_rgb_lock:
                self._preview_rgb = small
                self._preview_rgb_epoch += 1
            QTimer.singleShot(0, self, lambda e=ep: self._tick_preview_deferred(e))
        except Exception:
            logger.debug("webrtc rgb→preview failed", exc_info=True)

    def _tick_preview_deferred(self, epoch: int) -> None:
        """Игнорирует кадры, отложенные до разрыва TCP (иначе снова рисуется последний JPEG)."""
        if epoch != self._preview_epoch:
            return
        self._tick_preview()

    def _tick_preview(self) -> None:
        with self._preview_rgb_lock:
            rgb = self._preview_rgb
        if rgb is not None:
            try:
                import numpy as _np

                arr = rgb
                if isinstance(arr, _np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                    h, w = arr.shape[:2]
                    if not arr.flags["C_CONTIGUOUS"]:
                        arr = _np.ascontiguousarray(arr)
                    qimg = QImage(
                        arr.data,
                        w,
                        h,
                        w * 3,
                        QImage.Format.Format_RGB888,
                    ).copy()
                    pix = QPixmap.fromImage(qimg)
                    self._video_label.setPixmap(
                        _pixmap_scaled_cover(pix, self._video_label.size())
                    )
                    if self._stack.currentIndex() != 1:
                        self._stack.setCurrentIndex(1)
                    return
            except Exception:
                logger.debug("preview rgb failed", exc_info=True)

        with self._preview_lock:
            j = self._latest_jpeg
        if not j:
            return
        self._last_preview_jpeg = j
        pix = QPixmap()
        if not pix.loadFromData(j):
            qimg = QImage.fromData(j)
            if qimg.isNull():
                logger.warning("preview: could not decode JPEG (%d bytes)", len(j))
                return
            pix = QPixmap.fromImage(qimg)
        self._video_label.setPixmap(
            _pixmap_scaled_cover(pix, self._video_label.size())
        )
        if self._stack.currentIndex() != 1:
            self._stack.setCurrentIndex(1)
        self._apply_qr_visibility()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._apply_main_layout_geometry()
        super().resizeEvent(event)
        apply_windows_caption_brand(self)
        if self._last_preview_jpeg:
            j = self._last_preview_jpeg
            pix = QPixmap()
            if not pix.loadFromData(j):
                qimg = QImage.fromData(j)
                if not qimg.isNull():
                    pix = QPixmap.fromImage(qimg)
            if not pix.isNull():
                self._video_label.setPixmap(
                    _pixmap_scaled_cover(pix, self._video_label.size())
                )

    def _apply_qr_visibility(self) -> None:
        live = self._stack.currentIndex() == 1
        if self._idle_top is not None:
            self._idle_top.setVisible(not live)
        if hasattr(self, "_idle_top_peek") and self._idle_top_peek is not None:
            self._idle_top_peek.setVisible((not live) and (not self._idle_top_revealed))
        if live and self._idle_top_revealed:
            self._set_idle_top_revealed(False, animate=False)
        self._qr_main.setVisible(False)
        self._qr_meta_main.setVisible(False)
        self._update_qr()

    def _paint_qr(self, target: QLabel, max_side: int) -> None:
        token = self._token_edit.text().strip()
        port = self._port_spin.value()
        host = self._qr_host_for_phone()
        if not token:
            target.clear()
            return
        pc_name = self._get_pc_name()
        if self._enable_webrtc:
            payload = build_connect_payload(
                host,
                port,
                token,
                mode="webrtc",
                signaling_port=self._webrtc_signaling_port,
                name=pc_name,
            )
        else:
            payload = build_connect_payload(host, port, token, mode="tcp", name=pc_name)
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=2,
            )
            qr.add_data(payload)
            qr.make(fit=True)
            # Стандарт: чёрные модули на белом; затем фон → прозрачный, модули → белые.
            pil_img = qr.make_image(
                fill_color="#000000", back_color="#ffffff"
            ).convert("RGBA")
            px = pil_img.load()
            wimg, himg = pil_img.size
            for yy in range(himg):
                for xx in range(wimg):
                    r, g, b, a = px[xx, yy]
                    if r > 200 and g > 200 and b > 200:
                        px[xx, yy] = (0, 0, 0, 0)
                    else:
                        px[xx, yy] = (255, 255, 255, 255)
            buf = BytesIO()
            pil_img.save(buf, format="PNG", optimize=True)
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            target.setPixmap(
                pix.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        except Exception:
            logger.exception("QR render failed")
            target.setText("QR error")

    def _update_qr(self) -> None:
        token = self._token_edit.text().strip()
        host = self._qr_host_for_phone()
        if hasattr(self, "_idle_info") and self._idle_info is not None:
            if not token:
                self._idle_info.setText("Укажите токен или нажмите ↻, чтобы сгенерировать.")
            else:
                self._idle_info.setText("")
        if not token:
            if hasattr(self, "_qr_meta_set") and self._qr_meta_set is not None:
                self._qr_meta_set.setText("")
            if hasattr(self, "_qr_settings") and self._qr_settings is not None:
                self._qr_settings.clear()
            self._center_qr_cached = QPixmap()
            self._sync_idle_center_with_overlay_state()
            return
        if hasattr(self, "_qr_meta_set") and self._qr_meta_set is not None:
            self._qr_meta_set.setText("")
        if hasattr(self, "_qr_settings") and self._qr_settings is not None:
            self._paint_qr(self._qr_settings, 200)
            pm = self._qr_settings.pixmap()
            self._center_qr_cached = QPixmap() if pm is None else pm
            self._sync_idle_center_with_overlay_state()

    def _regen_token(self) -> None:
        self._token_edit.setText(secrets.token_urlsafe(12))

    def _append_status(self, text: str) -> None:
        logger.debug("state: %s", text)

    def _on_state(self, text: str) -> None:
        QTimer.singleShot(0, self, lambda t=text: self._append_status(t))
        # WebRTC "closed" или "failed" → вернуться на главный экран.
        # Эмитируем Signal: он безопасно переключает поток из фонового WebRTC-треда
        # в Qt main thread. Проверяем оба варианта состояния.
        if "WebRTC state: closed" in text or "WebRTC state: failed" in text:
            self._signal_webrtc_disconnected.emit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._connecting_dots_timer.stop()
        self._preview_timer.stop()
        if self._ndi is not None:
            self._ndi.stop()
            self._ndi = None
        if self._vcam is not None:
            self._vcam.stop()
            self._vcam = None
        if self._server is not None:
            self._server.stop()
            self._server = None
        if self._discovery_server is not None:
            self._discovery_server.stop()
            self._discovery_server = None
        self._stop_mdns()
        if self._webrtc_signaling is not None:
            self._webrtc_signaling.stop()
            self._webrtc_signaling = None
        if self._listen_was_cable:
            adb_reverse_remove(self._port_spin.value())
            adb_reverse_remove(DEFAULT_DISCOVERY_PORT)
            if self._enable_webrtc:
                adb_reverse_remove(self._webrtc_signaling_port)
        super().closeEvent(event)
