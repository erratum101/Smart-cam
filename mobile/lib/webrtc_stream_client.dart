import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

/// Согласовано с [fit_rgb_1920x1080] на ПК (numpy.rot90, k по mod 4).
int frameRotateKForDimensions(int width, int height) {
  final views = WidgetsBinding.instance.platformDispatcher.views;
  final deviceLandscape = views.isNotEmpty &&
      views.first.physicalSize.width > views.first.physicalSize.height;
  final frameLandscape = width > 0 && height > 0 && width > height;

  if (deviceLandscape && !frameLandscape) return 3;
  if (!deviceLandscape && !frameLandscape) return 3;
  if (!deviceLandscape && frameLandscape) return 1;
  return 0;
}

int frameRotateKForStream(MediaStream stream) {
  final tracks = stream.getVideoTracks();
  if (tracks.isEmpty) return 3;

  int dim(String key) {
    final v = tracks.first.getSettings()[key];
    if (v is num) return v.round();
    return 0;
  }

  return frameRotateKForDimensions(dim('width'), dim('height'));
}

/// TCP/JPEG: те же правила, что WebRTC; для USB добавляем 180° (сырой JPEG ≠ H.264).
int frameRotateKForTcpHello(int width, int height, {required bool cableLoopback}) {
  var k = frameRotateKForDimensions(width, height);
  if (cableLoopback) {
    k = (k + 2) % 4;
  }
  return k;
}

class WebRtcStreamClient {
  RTCPeerConnection? _pc;
  MediaStream? _stream;
  bool _connected = false;
  bool _disconnectNotified = false;
  bool _connecting = false;
  Timer? _disconnectTimer;
  Completer<void>? _connectCompleter;

  void Function()? onDisconnected;

  bool get isConnected => _connected && _pc != null;
  MediaStream? get localStream => _stream;

  void _onPeerConnectionState(RTCPeerConnectionState state) {
    if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
      _disconnectTimer?.cancel();
      _disconnectTimer = null;
      final c = _connectCompleter;
      if (c != null && !c.isCompleted) {
        c.complete();
      }
      return;
    }

    if (_connecting) {
      if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
          state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
        final c = _connectCompleter;
        if (c != null && !c.isCompleted) {
          c.completeError(StateError('WebRTC ICE/peer failed: $state'));
        }
      }
      return;
    }

    if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
        state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
      _disconnectTimer?.cancel();
      _disconnectTimer = null;
      unawaited(_notifyAndDisconnect());
      return;
    }
    if (state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected) {
      _disconnectTimer?.cancel();
      _disconnectTimer = Timer(const Duration(seconds: 4), () {
        if (_pc != null) {
          unawaited(_notifyAndDisconnect());
        }
      });
    }
  }

  Future<void> _waitUntilPeerConnected(
    RTCPeerConnection pc, {
    Duration timeout = const Duration(seconds: 12),
  }) async {
    if (pc.connectionState ==
        RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
      return;
    }
    _connectCompleter = Completer<void>();
    try {
      await _connectCompleter!.future.timeout(timeout);
    } on TimeoutException {
      throw StateError('WebRTC: ICE timeout (no media path to PC)');
    } finally {
      _connectCompleter = null;
    }
  }

  Future<void> connect({
    required String host,
    required int signalingPort,
    required String token,
    bool highQuality = false,
  }) async {
    await disconnect();
    _disconnectNotified = false;
    _disconnectTimer?.cancel();
    _disconnectTimer = null;

    final pc = await createPeerConnection({
      'sdpSemantics': 'unified-plan',
      'iceServers': <Map<String, dynamic>>[],
      // LAN/USB сценарий: TURN не нужен, поэтому экономим ICE-таймауты.
      'bundlePolicy': 'max-bundle',
      'rtcpMuxPolicy': 'require',
      // Уменьшает буферизацию и ускоряет старт картинки на ПК.
      'iceCandidatePoolSize': 0,
      'tcpCandidatePolicy': 'disabled',
    });
    _pc = pc;
    pc.onConnectionState = _onPeerConnectionState;

    // Wi‑Fi: 720p30 + умеренный битрейт — меньше задержка, чем 1080p60.
    final maxBitrate = highQuality ? 6 * 1000 * 1000 : 8 * 1000 * 1000;
    final minBitrate = highQuality ? 1500 * 1000 : 2 * 1000 * 1000;
    final maxFps = highQuality ? 30 : 60;
    final stream = await navigator.mediaDevices.getUserMedia({
      'audio': false,
      'video': highQuality
          ? {
              'facingMode': 'environment',
              'width': {'ideal': 1280},
              'height': {'ideal': 720},
              'aspectRatio': {'ideal': 1.7777777778},
              'frameRate': {'ideal': 30, 'max': 30},
            }
          : {
              'facingMode': 'environment',
              'width': 1280,
              'height': 720,
              'frameRate': 60,
            },
    });
    if (highQuality) {
      for (final t in stream.getVideoTracks()) {
        final s = t.getSettings();
        // ignore: avoid_print
        print(
          'webrtc capture: ${s['width']}x${s['height']} @ ${s['frameRate']}fps',
        );
      }
    }
    _stream = stream;
    for (final track in stream.getVideoTracks()) {
      final sender = await pc.addTrack(track, stream);

      // КРИТИЧНО: aiortc-VP8 декодер на ПК ломается на delta-кадрах от
      // Qualcomm OMX-VP8-энкодера (баг payload-descriptor parsing). Поэтому
      // здесь принудительно ставим H.264 в начало списка кодеков через
      // RTCRtpTransceiver.setCodecPreferences. На Android libwebrtc обычно
      // прячет H.264 в дефолтных офферах из-за лицензионных причин, но он
      // зарегистрирован как поддерживаемый и через codec preferences
      // выбирается без проблем. aiortc прекрасно декодирует H.264 через
      // avcodec без багов.
      try {
        final caps = await getRtpSenderCapabilities('video');
        final codecs = caps.codecs ?? <RTCRtpCodecCapability>[];
        // Лог: помогает диагностировать, если H.264 на этом железе
        // недоступен (например, на старой версии Android-вебвью).
        for (final c in codecs) {
          // ignore: avoid_print
          print('webrtc codec available: ${c.mimeType}');
        }
        final h264Baseline = <RTCRtpCodecCapability>[];
        final h264Other = <RTCRtpCodecCapability>[];
        final vp8 = <RTCRtpCodecCapability>[];
        final rest = <RTCRtpCodecCapability>[];
        for (final c in codecs) {
          final mt = c.mimeType.toLowerCase();
          if (mt == 'video/h264') {
            final sdp = (c.sdpFmtpLine ?? '').toLowerCase();
            if (sdp.contains('profile-level-id=42') ||
                sdp.contains('profile-level-id=420') ||
                sdp.contains('profile-level-id=42e')) {
              h264Baseline.add(c);
            } else {
              h264Other.add(c);
            }
          } else if (mt == 'video/vp8') {
            vp8.add(c);
          } else {
            rest.add(c);
          }
        }
        if (h264Baseline.isNotEmpty ||
            h264Other.isNotEmpty ||
            vp8.isNotEmpty) {
          final preferred = <RTCRtpCodecCapability>[
            ...h264Baseline,
            ...h264Other,
            ...vp8,
            ...rest,
          ];
          final transceivers = await pc.getTransceivers();
          for (final t in transceivers) {
            if (t.sender.senderId == sender.senderId) {
              await t.setCodecPreferences(preferred);
              break;
            }
          }
        }
      } on Object catch (e) {
        // ignore: avoid_print
        print('setCodecPreferences failed: $e');
      }

      // 1080p60 VP8 нужен битрейт 12-15 Мбит/с для чистой картинки. По USB
      // ADB-reverse (480 Мбит/с физически) и нормальному Wi-Fi 5 это
      // проходит без потерь. minBitrate 4 Мбит/с не даёт REMB просесть
      // в «кашу» при кратковременных задержках.
      try {
        final params = sender.parameters;
        final encodings = params.encodings ?? <RTCRtpEncoding>[];
        if (encodings.isEmpty) {
          encodings.add(
            RTCRtpEncoding(
              maxBitrate: maxBitrate,
              minBitrate: minBitrate,
              maxFramerate: maxFps,
            ),
          );
        } else {
          for (final e in encodings) {
            e.maxBitrate = maxBitrate;
            e.minBitrate = minBitrate;
            e.maxFramerate = maxFps;
            e.scaleResolutionDownBy = 1.0;
          }
        }
        params.encodings = encodings;
        params.degradationPreference = highQuality
            ? RTCDegradationPreference.MAINTAIN_FRAMERATE
            : RTCDegradationPreference.MAINTAIN_RESOLUTION;
        await sender.setParameters(params);
      } on Object {
        // некоторые версии flutter_webrtc не поддерживают часть полей
      }
    }

    final offer = await pc.createOffer({
      'offerToReceiveAudio': false,
      'offerToReceiveVideo': false,
    });
    await pc.setLocalDescription(offer);
    await _waitForIceGathering(pc);

    final local = await pc.getLocalDescription();
    if (local == null || (local.sdp ?? '').isEmpty) {
      throw StateError('Local SDP is empty');
    }
    final optimizedSdp = _optimizeOfferSdp(
      local.sdp!,
      sessionBitrateKbps: highQuality ? 6000 : 8000,
    );
    final frameRotateK = frameRotateKForStream(stream);

    final uri = Uri(
      scheme: 'http',
      host: host,
      port: signalingPort,
      path: '/webrtc/offer',
    );
    final resp = await http
        .post(
          uri,
          headers: {'content-type': 'application/json'},
          body: jsonEncode({
            'token': token,
            'type': local.type,
            'sdp': optimizedSdp,
            'frame_rotate_k': frameRotateK,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (resp.statusCode != 200) {
      throw StateError(
        'Signaling failed: HTTP ${resp.statusCode} ${resp.body}',
      );
    }
    final data = jsonDecode(resp.body);
    final answerSdp = '${data['sdp'] ?? ''}';
    final answerType = '${data['type'] ?? 'answer'}';
    if (answerSdp.isEmpty) {
      throw StateError('Signaling answer SDP is empty');
    }
    _connecting = true;
    try {
      await pc.setRemoteDescription(
        RTCSessionDescription(answerSdp, answerType),
      );
      await _waitUntilPeerConnected(pc);
      _connected = true;
    } finally {
      _connecting = false;
    }
  }

  Future<void> switchCamera() async {
    final stream = _stream;
    if (stream == null) return;
    final tracks = stream.getVideoTracks();
    if (tracks.isEmpty) return;
    await Helper.switchCamera(tracks.first);
  }

  Future<void> disconnect() async {
    _disconnectTimer?.cancel();
    _disconnectTimer = null;
    _connected = false;
    final pc = _pc;
    _pc = null;
    final stream = _stream;
    _stream = null;
    if (stream != null) {
      for (final t in stream.getTracks()) {
        await t.stop();
      }
      await stream.dispose();
    }
    if (pc != null) {
      await pc.close();
    }
  }

  Future<void> _waitForIceGathering(
    RTCPeerConnection pc, {
    Duration timeout = const Duration(seconds: 5),
  }) async {
    if (pc.iceGatheringState ==
        RTCIceGatheringState.RTCIceGatheringStateComplete) {
      return;
    }
    final c = Completer<void>();
    pc.onIceGatheringState = (state) {
      if (state == RTCIceGatheringState.RTCIceGatheringStateComplete &&
          !c.isCompleted) {
        c.complete();
      }
    };
    try {
      await c.future.timeout(timeout);
    } on TimeoutException {
      // Continue with current gathered candidates.
    }
  }

  Future<void> _notifyAndDisconnect() async {
    if (_connecting) return;
    await disconnect();
    if (_disconnectNotified) return;
    _disconnectNotified = true;
    onDisconnected?.call();
  }

  /// Преднастраивает SDP-offer под максимальное качество в LAN/USB и
  /// заставляет договариваться по H.264, а не VP8, причём с уровнем
  /// **5.1** (1080p60, 4K30, и выше).
  ///
  /// Ключевые причины:
  /// 1. Хардверный VP8 от `OMX.qcom.video.encoder.vp8` на Qualcomm пишет
  ///    payload-descriptor флаги, которые aiortc-Vp8Depayloader неправильно
  ///    парсит — на ПК сыпется `Vp8Decoder() failed to decode, Invalid
  ///    data` для каждого пакета и в OBS не приходит ни одного кадра.
  /// 2. H.264 поддерживается всеми Qualcomm/Exynos/Mediatek хардверными
  ///    энкодерами и идеально декодируется avcodec-h264 в aiortc.
  /// 3. ПРОБЛЕМА: libwebrtc-Android по дефолту объявляет H.264 максимум
  ///    Level 3.1 (`profile-level-id=...1f`) — это 720p30. При попытке
  ///    реально кодировать 1080p60 на этом профиле Qualcomm OMX встаёт
  ///    в degraded state (Level1), стрим обрывается. Нужно поднять
  ///    `level_idc` хотя бы до Level 4.2 (`...2a`), а лучше Level 5.1
  ///    (`...33`) — тогда encoder спокойно работает в 1080p60.
  ///
  /// Делает:
  /// 1. Переставляет `m=video` PT-список так, чтобы H.264 шёл первым —
  ///    aiortc выберет именно его при answer.
  /// 2. Поднимает `b=AS:15000` (15 Мбит/с).
  /// 3. ПЕРЕПИСЫВАЕТ существующие `profile-level-id` в H.264 fmtp на
  ///    Level 5.1 (`33`), сохраняя байт profile_idc/iop без изменений.
  ///    Это критично: aiortc-receiver получит и матчнёт `33`-уровень
  ///    (мы добавили его в CODECS на десктопе), libwebrtc-Android
  ///    сконфигурирует Qualcomm OMX в Level 5.1, и 1080p60 потечёт.
  String _optimizeOfferSdp(String sdp, {int sessionBitrateKbps = 8000}) {
    final asKbps = sessionBitrateKbps.clamp(2000, 20000);
    final tias = asKbps * 1000;
    final lines = sdp.split('\r\n');
    final h264Payloads = <String>{};
    final vp8Payloads = <String>{};
    var inVideo = false;
    for (final line in lines) {
      if (line.startsWith('m=')) {
        inVideo = line.startsWith('m=video ');
        continue;
      }
      if (!inVideo) continue;
      if (line.startsWith('a=rtpmap:')) {
        final rest = line.substring('a=rtpmap:'.length);
        final pt = rest.split(' ').first.trim();
        if (rest.contains('H264/90000')) {
          h264Payloads.add(pt);
        } else if (rest.contains('VP8/90000')) {
          vp8Payloads.add(pt);
        }
      }
    }

    final out = <String>[];
    inVideo = false;
    var insertedBitrate = false;
    for (final line in lines) {
      if (line.startsWith('m=')) {
        if (line.startsWith('m=video ') && h264Payloads.isNotEmpty) {
          final parts = line.split(' ');
          if (parts.length >= 4) {
            final header = parts.sublist(0, 3);
            final pts = parts.sublist(3);
            final h264First = <String>[];
            final rest = <String>[];
            for (final pt in pts) {
              if (h264Payloads.contains(pt)) {
                h264First.add(pt);
              } else {
                rest.add(pt);
              }
            }
            out.add([...header, ...h264First, ...rest].join(' '));
            inVideo = true;
            insertedBitrate = false;
            continue;
          }
        }
        inVideo = line.startsWith('m=video ');
        insertedBitrate = false;
        out.add(line);
        continue;
      }
      // Поднимаем H.264 level до 5.1 во всех существующих fmtp.
      if (inVideo && line.startsWith('a=fmtp:')) {
        final patched = _bumpH264LevelTo51(line, h264Payloads);
        out.add(patched);
        if (!insertedBitrate) {
          // safeguard: уже добавили
        }
        continue;
      }
      out.add(line);
      if (inVideo && !insertedBitrate && line.startsWith('c=')) {
        out.add('b=AS:$asKbps');
        out.add('b=TIAS:$tias');
        insertedBitrate = true;
      }
    }

    final withFmtp = <String>[];
    final existingFmtp = <String>{};
    for (final line in out) {
      withFmtp.add(line);
      if (line.startsWith('a=fmtp:')) {
        final pt = line.substring('a=fmtp:'.length).split(' ').first.trim();
        if (pt.isNotEmpty) {
          existingFmtp.add(pt);
        }
      }
    }
    // Если у H.264-PT не было своего fmtp (редко, но бывает) — добавим
    // CBP Level 5.1 явно.
    for (final pt in h264Payloads) {
      if (existingFmtp.contains(pt)) continue;
      withFmtp.add(
        'a=fmtp:$pt level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e033',
      );
    }
    for (final pt in vp8Payloads) {
      if (existingFmtp.contains(pt)) continue;
      withFmtp.add(
        'a=fmtp:$pt x-google-start-bitrate=8000;x-google-max-bitrate=15000;x-google-min-bitrate=4000',
      );
    }
    return withFmtp.join('\r\n');
  }

  /// Заменяет последний байт `profile-level-id` (`level_idc`) на `33`
  /// (Level 5.1) для всех H.264 PT, сохраняя `profile_idc` и `profile_iop`.
  String _bumpH264LevelTo51(String fmtpLine, Set<String> h264Pts) {
    final colon = fmtpLine.indexOf(':');
    final space = fmtpLine.indexOf(' ');
    if (colon < 0 || space < 0 || space <= colon) return fmtpLine;
    final pt = fmtpLine.substring(colon + 1, space).trim();
    if (!h264Pts.contains(pt)) return fmtpLine;
    final params = fmtpLine.substring(space + 1);
    final regex = RegExp('profile-level-id=([0-9a-fA-F]{6})');
    final m = regex.firstMatch(params);
    if (m == null) return fmtpLine;
    final orig = m.group(1)!;
    // Сохраняем profile_idc (первые 2) и profile_iop (следующие 2),
    // меняем только level_idc (последние 2) на `33` = 51 = Level 5.1.
    final patched =
        '${orig.substring(0, 4)}33'.toLowerCase();
    final newParams = params.replaceFirst(regex, 'profile-level-id=$patched');
    return 'a=fmtp:$pt $newParams';
  }
}
