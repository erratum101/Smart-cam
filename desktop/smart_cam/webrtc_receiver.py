"""Desktop WebRTC video receiver backed by aiortc."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

import numpy as np

from .frame_fit import fit_rgb_1920x1080
from .frame_store import FrameStore
from aiortc import RTCPeerConnection, RTCSessionDescription

logger = logging.getLogger(__name__)


# --- Patch aiortc CODECS to advertise H.264 Level 5.1 (1080p60) -----------------
# aiortc по дефолту регистрирует H.264 только с profile-level-id `42001f` и
# `42e01f` — оба это Level 3.1 (макс 720p30). При 1080p60 libwebrtc-Android
# в SDP-answer от aiortc видит максимум Level 3.1 и обрезает Qualcomm
# encoder до Level 1 (некорректное состояние), картинка не идёт, peer
# connection обрывается.
#
# `find_common_codecs` в aiortc выбирает ПЕРВЫЙ локальный кодек, у которого
# совпадает H.264-профиль (level игнорируется при матчинге, но идёт в
# answer-SDP «как есть»). Поэтому недостаточно ДОБАВИТЬ entries с Level 5.1
# — их не выберут. Нужно ПЕРЕЗАПИСАТЬ существующие entries, подняв уровень.
#
# H.264-decoder в aiortc — это avcodec (через pyav), он поддерживает любой
# Level. Профиль/уровень в SDP — это только negotiation hint, поэтому можно
# безопасно повысить уровень и получить нативное 1080p60 от Qualcomm OMX.
def _install_h264_level_patch() -> None:
    try:
        from aiortc.codecs import CODECS as _CODECS  # noqa: WPS433
        from aiortc.rtcrtpparameters import (  # noqa: WPS433
            RTCRtcpFeedback as _RTCFb,
            RTCRtpCodecParameters as _RTCCP,
        )
    except Exception:
        return

    video = _CODECS.get("video") or []
    patched_existing = 0
    for c in video:
        if c.mimeType != "video/H264":
            continue
        plid = c.parameters.get("profile-level-id", "")
        if not plid or len(plid) != 6:
            continue
        if plid.lower().endswith("33"):
            continue
        new_plid = f"{plid[:4]}33".lower()
        c.parameters["profile-level-id"] = new_plid
        patched_existing += 1

    # Constrained Baseline Level 5.1 — low latency (no B-frames), 720p/1080p60.
    has_cbp = any(
        c.mimeType == "video/H264"
        and c.parameters.get("profile-level-id", "").lower().startswith("42e")
        for c in video
    )
    extra: list[tuple[str, str]] = []
    if not has_cbp:
        extra.append(("42e033", "video/H264"))

    if extra:
        used_pts = {c.payloadType for c in video}
        next_pt = (max(used_pts) + 1) if used_pts else 97
        for plid, mt in extra:
            while next_pt in used_pts or next_pt + 1 in used_pts:
                next_pt += 1
            video.append(
                _RTCCP(
                    mimeType=mt,
                    clockRate=90000,
                    payloadType=next_pt,
                    rtcpFeedback=[
                        _RTCFb(type="nack"),
                        _RTCFb(type="nack", parameter="pli"),
                        _RTCFb(type="goog-remb"),
                    ],
                    parameters={
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": plid,
                    },
                )
            )
            video.append(
                _RTCCP(
                    mimeType="video/rtx",
                    clockRate=90000,
                    payloadType=next_pt + 1,
                    parameters={"apt": next_pt},
                )
            )
            used_pts.update({next_pt, next_pt + 1})
            next_pt += 2

    logger.info(
        "H.264 capabilities patched: %d existing bumped to L5.1, %d extra added, total H264 entries=%d",
        patched_existing,
        len(extra),
        len([c for c in video if c.mimeType == "video/H264"]),
    )


_install_h264_level_patch()


# --- Patch aiortc Vp8Decoder to recover from invalid-data errors ----------------
# Qualcomm OMX VP8-encoder ставит payload-descriptor флаги, на которых
# libvpx через avcodec падает с `Invalid data found when processing input`.
# Базовая реализация просто логирует ворнинг и возвращает [], что приводит
# к бесконечному «всё валится» — никогда не приходит recovery-кадр.
# Наш патч пересоздаёт codec context при подряд идущих ошибках, чтобы
# сбросить внутреннее состояние avcodec и спокойно подхватить следующий
# keyframe (который мы периодически запрашиваем по PLI ниже).
def _install_vp8_recovery_patch() -> None:
    try:
        from aiortc.codecs import vpx as _vpx  # noqa: WPS433
        import av as _av  # noqa: WPS433
        from av import CodecContext as _CodecContext  # noqa: WPS433
        from av.packet import Packet as _Packet  # noqa: WPS433
        from aiortc.mediastreams import VIDEO_TIME_BASE as _VTB  # noqa: WPS433
    except Exception:
        return
    if getattr(_vpx.Vp8Decoder, "_smartcam_patched", False):
        return

    original_init = _vpx.Vp8Decoder.__init__
    original_decode = _vpx.Vp8Decoder.decode

    def _patched_init(self) -> None:  # type: ignore[no-untyped-def]
        original_init(self)
        self._smartcam_fail_count = 0

    def _patched_decode(self, encoded_frame):  # type: ignore[no-untyped-def]
        try:
            packet = _Packet(encoded_frame.data)
            packet.pts = encoded_frame.timestamp
            packet.time_base = _VTB
            frames = list(self.codec.decode(packet))
            self._smartcam_fail_count = 0
            return frames
        except _av.FFmpegError as e:
            self._smartcam_fail_count += 1
            if self._smartcam_fail_count <= 3:
                logger.warning(
                    "Vp8Decoder() failed to decode (%d in a row), waiting for keyframe: %s",
                    self._smartcam_fail_count, e,
                )
            elif self._smartcam_fail_count == 4:
                # Полный сброс libvpx — следующий keyframe гарантированно подхватим.
                logger.warning(
                    "Vp8Decoder(): too many failures, recreating libvpx context"
                )
                try:
                    self.codec = _CodecContext.create("libvpx", "r")
                except Exception:
                    pass
            return []

    _vpx.Vp8Decoder.__init__ = _patched_init  # type: ignore[assignment]
    _vpx.Vp8Decoder.decode = _patched_decode  # type: ignore[assignment]
    _vpx.Vp8Decoder._smartcam_patched = True  # type: ignore[attr-defined]
    logger.info("Vp8Decoder recovery patch installed")


_install_vp8_recovery_patch()


# --- Patch aiortc H264Decoder to recover from invalid-data errors ----------------
# Хардверный H.264 от Qualcomm OMX отдаёт SPS/PPS только при keyframe. Если
# из-за потери одного RTP-пакета ломается FU-A reassembly или просто
# проскакивает сбой состояния avcodec, ВСЕ последующие P-кадры выпадают
# с `Invalid data found when processing input: avcodec_send_packet()`.
#
# Решаем как и для VP8:
# 1. Считаем подряд идущие ошибки декодирования.
# 2. После 3-х подряд — просим PLI у источника (через _smartcam_pli_callback,
#    который установит WebRtcSessionManager).
# 3. После 6 подряд — пересоздаём CodecContext, чтобы avcodec сбросил
#    внутреннее состояние и спокойно подхватил следующий keyframe.
def _install_h264_recovery_patch() -> None:
    try:
        from aiortc.codecs import h264 as _h264  # noqa: WPS433
        import av as _av  # noqa: WPS433
        from av import CodecContext as _CodecContext  # noqa: WPS433
        from av.packet import Packet as _Packet  # noqa: WPS433
        from aiortc.mediastreams import VIDEO_TIME_BASE as _VTB  # noqa: WPS433
    except Exception:
        return
    if getattr(_h264.H264Decoder, "_smartcam_patched", False):
        return

    original_init = _h264.H264Decoder.__init__

    def _patched_init(self) -> None:  # type: ignore[no-untyped-def]
        original_init(self)
        self._smartcam_fail_count = 0

    def _patched_decode(self, encoded_frame):  # type: ignore[no-untyped-def]
        try:
            packet = _Packet(encoded_frame.data)
            packet.pts = encoded_frame.timestamp
            packet.time_base = _VTB
            frames = list(self.codec.decode(packet))
            self._smartcam_fail_count = 0
            return frames
        except _av.FFmpegError as e:
            self._smartcam_fail_count += 1
            if self._smartcam_fail_count <= 3:
                logger.warning(
                    "H264Decoder() failed to decode (%d in a row), requesting keyframe: %s",
                    self._smartcam_fail_count, e,
                )
            # Каждые 3 подряд ошибки — сбрасываем кодек И просим PLI.
            # fail_count сбрасывается в 0, чтобы цикл повторялся для каждой
            # новой серии ошибок. Без сброса счётчика PLI отправляется только
            # один раз (при строго 3/6) и больше никогда.
            if self._smartcam_fail_count % 3 == 0:
                logger.warning(
                    "H264Decoder(): %d consecutive failures, recreating codec + PLI",
                    self._smartcam_fail_count,
                )
                try:
                    self.codec = _CodecContext.create("h264", "r")
                except Exception:
                    logger.debug("h264 codec recreate failed", exc_info=True)
                # Сбрасываем счётчик: следующая серия ошибок тоже даст PLI через 3.
                self._smartcam_fail_count = 0
                cb = getattr(_h264, "_smartcam_pli_callback", None)
                if callable(cb):
                    try:
                        cb()
                    except Exception:
                        logger.debug("h264 pli callback failed", exc_info=True)
            return []

    _h264.H264Decoder.__init__ = _patched_init  # type: ignore[assignment]
    _h264.H264Decoder.decode = _patched_decode  # type: ignore[assignment]
    _h264.H264Decoder._smartcam_patched = True  # type: ignore[attr-defined]
    logger.info("H264Decoder recovery patch installed")


_install_h264_recovery_patch()


def _decode_frame_to_output(frame, rotate_k: int) -> np.ndarray:
    """YUV→RGB + fit in one executor job (sync)."""
    rgb = frame.to_ndarray(format="rgb24")
    if not rgb.flags["C_CONTIGUOUS"]:
        rgb = np.ascontiguousarray(rgb)
    return fit_rgb_1920x1080(rgb, rotate_k=rotate_k)


class WebRtcSessionManager:
    """Accepts one active WebRTC sender and publishes decoded RGB to FrameStore."""

    def __init__(
        self,
        frame_store: FrameStore,
        on_state: Callable[[str], None] | None = None,
        on_rgb_frame: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        self._frame_store = frame_store
        self._on_state = on_state
        # Колбек получает каждый декодированный RGB-кадр (np.uint8, HxWx3).
        # Используется UI-частью, чтобы показать живое превью на ПК — без
        # него превью на десктопе остаётся чёрным, потому что VCamWorker
        # успевает забрать кадры из очереди раньше, чем GUI-таймер.
        self._on_rgb_frame = on_rgb_frame
        self._pcs: dict[str, RTCPeerConnection] = {}
        self._accept_lock = asyncio.Lock()
        self._latest_session: str | None = None
        self._frames = 0
        self._drops = 0
        self._fps_clock = 0.0
        self._effective_fps = 0.0
        self._frame_rotate_k = 0
        self._decode_busy = False

    def _emit(self, text: str) -> None:
        if self._on_state:
            try:
                self._on_state(text)
            except Exception:
                logger.exception("webrtc on_state failed")

    async def close(self) -> None:
        for sid, pc in list(self._pcs.items()):
            try:
                await pc.close()
            except Exception:
                logger.debug("pc.close failed: %s", sid, exc_info=True)
            self._pcs.pop(sid, None)
        self._latest_session = None
        self._emit("WebRTC receiver stopped")

    def stats(self) -> dict[str, float | int]:
        return {
            "frames": self._frames,
            "drops": self._drops,
            "effective_fps": round(self._effective_fps, 2),
        }

    async def accept_offer(
        self,
        sdp: str,
        sdp_type: str = "offer",
        *,
        frame_rotate_k: int = 0,
    ) -> tuple[str, str]:
        async with self._accept_lock:
            self._frame_rotate_k = int(frame_rotate_k) % 4
            # Keep one active sender at a time for deterministic behavior.
            if self._latest_session and self._latest_session in self._pcs:
                old = self._pcs.pop(self._latest_session)
                try:
                    await old.close()
                except Exception:
                    logger.debug("close old pc failed", exc_info=True)

            sid = uuid.uuid4().hex
            pc = RTCPeerConnection()
            self._pcs[sid] = pc
            self._latest_session = sid
            self._emit("WebRTC: peer connected")

            # Регистрируем PLI-колбек глобально в aiortc.codecs.h264, чтобы
            # пропатченный H264Decoder.decode мог попросить keyframe прямо
            # из синхронного потока декодирования.
            try:
                from aiortc.codecs import h264 as _h264_mod  # noqa: WPS433

                loop = asyncio.get_running_loop()

                def _request_keyframe() -> None:
                    if sid not in self._pcs or self._pcs.get(sid) is not pc:
                        return
                    asyncio.run_coroutine_threadsafe(
                        self._send_pli_now(pc), loop
                    )

                _h264_mod._smartcam_pli_callback = _request_keyframe  # type: ignore[attr-defined]
            except Exception:
                logger.debug("could not install h264 pli callback", exc_info=True)

            @pc.on("connectionstatechange")
            async def on_connectionstatechange() -> None:
                st = pc.connectionState
                self._emit(f"WebRTC state: {st}")
                if st in ("failed", "closed"):
                    try:
                        await pc.close()
                    except Exception:
                        pass
                    self._pcs.pop(sid, None)

            @pc.on("track")
            def on_track(track) -> None:  # type: ignore[no-untyped-def]
                if track.kind != "video":
                    return
                self._emit("WebRTC: video track received")
                asyncio.create_task(self._consume_video(track, sid))

            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=sdp_type))
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # Wait for ICE gathering so answer SDP includes candidates.
            await self._wait_for_ice_complete(pc)
            local = pc.localDescription
            if local is None:
                raise RuntimeError("localDescription is empty")
            chosen = self._negotiated_video_codec(local.sdp)
            if chosen:
                logger.info("WebRTC negotiated video codec: %s", chosen)
                self._emit(f"WebRTC codec: {chosen}")
            return sid, local.sdp

    async def _wait_for_ice_complete(self, pc: RTCPeerConnection, timeout_s: float = 5.0) -> None:
        if pc.iceGatheringState == "complete":
            return
        loop = asyncio.get_running_loop()
        done = loop.create_future()

        @pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange() -> None:
            if pc.iceGatheringState == "complete" and not done.done():
                done.set_result(True)

        try:
            await asyncio.wait_for(done, timeout=timeout_s)
        except TimeoutError:
            logger.debug("ICE gather timeout, continue with partial candidates")

    async def _consume_video(self, track, sid: str) -> None:  # type: ignore[no-untyped-def]
        import functools as _functools

        loop = asyncio.get_running_loop()
        first_frame_logged = False
        rotate_k = self._frame_rotate_k
        while True:
            if sid not in self._pcs:
                break
            try:
                frame = await track.recv()
            except Exception:
                break
            # Пока декодируем прошлый кадр — не копим очередь (главная причина
            # многосекундной задержки при 1080p + LANCZOS на каждом кадре).
            if self._decode_busy:
                continue
            self._decode_busy = True
            try:
                rgb = await loop.run_in_executor(
                    None,
                    _functools.partial(_decode_frame_to_output, frame, rotate_k),
                )
            except Exception:
                logger.debug("frame decode/fit failed", exc_info=True)
                continue
            finally:
                self._decode_busy = False
            try:
                if not first_frame_logged:
                    h, w = rgb.shape[:2]
                    logger.info("WebRTC first frame (normalized): %dx%d", w, h)
                    self._emit(f"WebRTC: кадр {w}×{h}")
                    first_frame_logged = True
                self._frames += 1
                self._frame_store.publish(rgb)
                if self._on_rgb_frame is not None:
                    try:
                        self._on_rgb_frame(rgb)
                    except Exception:
                        logger.debug("on_rgb_frame failed", exc_info=True)
            except Exception:
                logger.debug("frame publish failed", exc_info=True)
                continue

    async def _send_pli_now(self, pc: RTCPeerConnection) -> None:
        """Отстреливает один PLI-пакет на все video-receiver'ы peer-connection.

        Используется и периодическим PLI-loop'ом, и пропатченным H264Decoder
        при detection ошибок декодирования (через _smartcam_pli_callback).
        """
        for receiver in pc.getReceivers():
            track = getattr(receiver, "track", None)
            if track is None or getattr(track, "kind", "") != "video":
                continue
            try:
                # _send_rtcp_pli ждёт media_ssrc — это ssrc remote-стрима;
                # _RTCRtpReceiver__remote_streams хранит mapping.
                remote = getattr(
                    receiver, "_RTCRtpReceiver__remote_streams", {}
                )
                for media_ssrc in list(remote.keys()):
                    await receiver._send_rtcp_pli(media_ssrc)
            except Exception:
                logger.debug("pli send failed", exc_info=True)

    @staticmethod
    def _negotiated_video_codec(sdp: str) -> str:
        """Возвращает читаемое имя выбранного видео-кодека из локального SDP."""
        in_video = False
        first_pt: str | None = None
        rtpmaps: dict[str, str] = {}
        for raw in (sdp or "").split("\n"):
            line = raw.rstrip("\r")
            if line.startswith("m="):
                in_video = line.startswith("m=video ")
                if in_video:
                    parts = line.split(" ")
                    if len(parts) >= 4:
                        first_pt = parts[3]
                continue
            if not in_video:
                continue
            if line.startswith("a=rtpmap:"):
                rest = line.split(":", 1)[1]
                pt, codec = rest.split(" ", 1)
                rtpmaps[pt.strip()] = codec.strip()
        if first_pt and first_pt in rtpmaps:
            return rtpmaps[first_pt]
        return ""

