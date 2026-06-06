import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' show FilterQuality;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart' as rtc;
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'discovery_service.dart';
import 'jpeg_encoder_isolate.dart';
import 'protocol.dart';
import 'qr_config.dart';
import 'qr_scan_screen.dart';
import 'stream_client.dart';
import 'webrtc_stream_client.dart';

/// Совпадает с логикой [CameraPreview]: в портрете виджет превью имеет соотношение сторон 1/aspectRatio.
bool _cameraValueIsLandscape(CameraValue v) {
  if (v.isRecordingVideo && v.recordingOrientation != null) {
    final o = v.recordingOrientation!;
    return o == DeviceOrientation.landscapeLeft ||
        o == DeviceOrientation.landscapeRight;
  }
  final o =
      v.previewPauseOrientation ??
      v.lockedCaptureOrientation ??
      v.deviceOrientation;
  return o == DeviceOrientation.landscapeLeft ||
      o == DeviceOrientation.landscapeRight;
}

enum _ViewMode { scanner, camera }

/// Доп. отступ под статус-бар (часы, сеть, вырез) на экране трансляции.
const _kStreamOverlayTopExtra = 12.0;

/// Качество исходящего потока (JPEG + частота кадров).
enum StreamConnectionQuality { low, medium, high }

extension StreamConnectionQualityWire on StreamConnectionQuality {
  /// Индекс для wire-протокола (HELLO), 0..2.
  int get wireIndex => switch (this) {
    StreamConnectionQuality.low => 0,
    StreamConnectionQuality.medium => 1,
    StreamConnectionQuality.high => 2,
  };
}

/// JPEG quality по индексу из HELLO_OK (= запрос телефона).
int jpegQualityForNegotiatedStream(int q) => switch (q) {
  // 0 — аварийный USB/TCP; 1 — средний; 2 — Wi‑Fi/LAN.
  0 => 35,
  1 => 72,
  2 => 88,
  _ => 35,
};

Duration streamIntervalForNegotiatedStream(int q) => switch (q) {
  0 => const Duration(milliseconds: 200),
  1 => const Duration(milliseconds: 50),
  2 => const Duration(milliseconds: 33),
  _ => const Duration(milliseconds: 200),
};

const _kStreamQualityPrefKey = 'stream_connection_quality';
const _kSavedHostKey = 'saved_host';
const _kSavedPortKey = 'saved_port';
const _kSavedTokenKey = 'saved_token';
const _kSavedModeKey = 'saved_mode';
const _kSavedSignalingPortKey = 'saved_signaling_port';
const _kRecentConnectionsKey = 'recent_connections';
const _kMaxRecentConnections = 5;
// WebRTC на LAN; TCP/JPEG — fallback (~5 fps) и единственный путь по USB
// (127.0.0.1 / adb reverse: сигналинг HTTP ок, ICE/UDP для WebRTC — нет).
const _forceTcpTransport = false;
// Если QR/обнаружение не сообщили signaling-порт, эвристически считаем его
// `streamPort + 1` (десктоп так и поднимает aiortc). Позволяет включить
// WebRTC даже для «недавних» подключений, сохранённых до апдейта.
const _kSignalingPortOffsetFallback = 1;

/// Основной задний фон экрана (#002EE8 — как десктоп idle).
const Color kAppScreenBackground = Color(0xFF002EE8);

const List<double> _kBrandRingRatios = [
  1.00,
  0.90,
  0.80,
  0.70,
  0.60,
  0.50,
  0.42,
  0.34,
  0.26,
  0.18,
];

/// Нативный десктоп (Windows / macOS / Linux): круги с внутренней «тенью» вместо [BoxShadow].
bool _sessionTargetUsesInnerCircleShading() {
  if (kIsWeb) return false;
  return defaultTargetPlatform == TargetPlatform.windows ||
      defaultTargetPlatform == TargetPlatform.macOS ||
      defaultTargetPlatform == TargetPlatform.linux;
}

/// Вынесено из [State] — стабильнее при hot reload, чем приватный метод state.
///
/// [pullSheet] — [DraggableScrollableSheet] по центру стека, **между** кольцами и логотипом,
/// чтобы слайдер не перекрывался непрозрачным фоном.
Widget _buildBrandIdleWaveFrame({
  required double phase,
  required bool centerShowsQrIcon,
  required VoidCallback? onCenterTap,
  required double pullProgress,
  Widget? pullSheet,
}) {
  final t = pullProgress.clamp(0.0, 1.0);
  const shadowDyOpen = -11.0;
  final ringShadowOffset = Offset(0, shadowDyOpen * t);
  const ringColor = Color(0xFF002EE8);
  const bgColor = kAppScreenBackground;
  final smallestIdx = _kBrandRingRatios.length - 1;

  return LayoutBuilder(
    builder: (context, constraints) {
      final baseDiameter = constraints.maxHeight * 1.06;
      final centerY = constraints.maxHeight * 0.5;
      final centerX = constraints.maxWidth * 0.5;
      final logoWave = math.sin(phase - smallestIdx * 0.55);
      final logoScale = 1.0 + logoWave * 0.058;
      final baseLogo = baseDiameter * 0.16;

      // Фон и кольца не участвуют в hit-test — тапы проходят к нижнему листу;
      // иконка сверху без IgnorePointer, иначе DraggableScrollableSheet перехватывал бы нажатия.
      return Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: ColoredBox(
                color: bgColor,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    ...List.generate(_kBrandRingRatios.length, (i) {
                      final baseD = baseDiameter * _kBrandRingRatios[i];
                      final wave = math.sin(phase - i * 0.55);
                      final scale = 1.0 + wave * 0.013;
                      return Positioned(
                        left: centerX - baseD / 2,
                        top: centerY - baseD / 2,
                        child: Transform.scale(
                          scale: scale,
                          alignment: Alignment.center,
                          filterQuality: FilterQuality.medium,
                          child: SizedBox(
                            width: baseD,
                            height: baseD,
                            child: _sessionTargetUsesInnerCircleShading()
                                ? ClipOval(
                                    child: Stack(
                                      fit: StackFit.expand,
                                      children: [
                                        const ColoredBox(color: ringColor),
                                        DecoratedBox(
                                          decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            gradient: RadialGradient(
                                              center: Alignment(
                                                0,
                                                0.32 + 0.12 * t,
                                              ),
                                              radius: 1.02,
                                              colors: [
                                                Colors.transparent,
                                                Colors.black.withValues(
                                                  alpha: 0.08 + 0.04 * t,
                                                ),
                                              ],
                                              stops: const [0.71, 1.0],
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  )
                                : Container(
                                    width: baseD,
                                    height: baseD,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: ringColor,
                                      boxShadow: [
                                        BoxShadow(
                                          color: Colors.black.withValues(
                                            alpha: 0.08 + 0.04 * t,
                                          ),
                                          blurRadius: 10 + 4 * t,
                                          spreadRadius: 0,
                                          offset: ringShadowOffset,
                                        ),
                                      ],
                                    ),
                                  ),
                          ),
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
          ),
          if (pullSheet != null) Positioned.fill(child: pullSheet),
          Positioned(
            left: centerX - baseLogo / 2,
            top: centerY - baseLogo / 2,
            child: Transform.scale(
              scale: logoScale,
              alignment: Alignment.center,
              filterQuality: FilterQuality.medium,
              child: GestureDetector(
                onTap: onCenterTap,
                behavior: HitTestBehavior.opaque,
                child: SizedBox(
                  width: baseLogo,
                  height: baseLogo,
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 320),
                    switchInCurve: Curves.easeOutCubic,
                    switchOutCurve: Curves.easeInCubic,
                    transitionBuilder: (child, anim) {
                      return FadeTransition(
                        opacity: anim,
                        child: ScaleTransition(
                          scale: Tween<double>(
                            begin: 0.88,
                            end: 1,
                          ).animate(anim),
                          child: child,
                        ),
                      );
                    },
                    child: centerShowsQrIcon
                        ? Icon(
                            Icons.qr_code_scanner_rounded,
                            key: const ValueKey('center_qr'),
                            color: Colors.white,
                            size: baseLogo * 0.56,
                          )
                        : SvgPicture.asset(
                            'assets/iconnobg.svg',
                            key: const ValueKey('center_logo'),
                            width: baseLogo,
                            height: baseLogo,
                          ),
                  ),
                ),
              ),
            ),
          ),
        ],
      );
    },
  );
}

/// Home: QR scanner first (tracking frame), bottom controls, camera preview / stream.
class SessionHomePage extends StatefulWidget {
  const SessionHomePage({super.key});

  @override
  State<SessionHomePage> createState() => _SessionHomePageState();
}

class _SessionHomePageState extends State<SessionHomePage> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final _hostCtrl = TextEditingController();
  final _portCtrl = TextEditingController(text: '17777');
  final _tokenCtrl = TextEditingController();

  MobileScannerController? _scanner;

  /// Только для полноэкранного QR, когда основной [_scanner] ещё нет (например, во время превью камеры).
  MobileScannerController? _qrOverlayOnlyController;
  bool _qrFullscreenOpen = false;
  CameraController? _camera;
  final _client = StreamClient();
  final _webrtcClient = WebRtcStreamClient();
  final rtc.RTCVideoRenderer _webrtcPreview = rtc.RTCVideoRenderer();
  // Воркер-изолят, в нём идёт YUV→RGB→JPEG (TCP/JPEG fallback). Без него
  // тяжёлый цикл блокировал бы UI-изолят и вся анимация заикалась бы.
  final JpegEncoder _jpegEncoder = JpegEncoder();
  QrConnectConfig? _lastQrConfig;
  bool _streamViaWebRtc = false;

  /// Главный экран: первое нажатие по центру — плавно лого→QR; второе — открыть сканер.
  bool _idleCenterQrPrimed = false;

  _ViewMode _mode = _ViewMode.scanner;
  bool _streaming = false;
  bool _streamStartInFlight = false;
  bool _webrtcPreviewReady = false;
  bool _busy = false;

  /// Не рисовать [CameraPreview] на кадр dispose→сканер, чтобы не мигал красный экран.
  bool _suppressCameraPreview = false;

  /// Сдвиг полносканого QR вправо; подложка при открытом сканере в начале свайпа смещена
  /// влево на 30% ширины и по мере свайпа возвращается вправо (к нулю).
  double _qrBackdropDragX = 0;

  /// Сдвиг карточки трансляции при свайпе вправо (назад на главный экран).
  double _streamDragX = 0;
  bool _streamDismissing = false;

  static const double _kIdleSheetMin = 0.10;
  static const double _kIdleSheetMax = 0.36;
  static const double _kIdlePullConnectLabel = 0.115;
  static const double _kIdleHandleBlockBase = 88;
  static const double _kIdleHandleHelperExtra = 46;
  double _idleSheetExtent = _kIdleSheetMin;

  /// Главный экран: лист «Подключение» и нижняя панель — не на экране трансляции.
  bool get _showIdleConnectionChrome => !_streaming && !_streamStartInFlight;

  /// 0…1: насколько раскрыт нижний лист (тени колец, смена логотипа на иконку QR).
  double get _idlePullProgress {
    final span = _kIdleSheetMax - _kIdleSheetMin;
    if (span <= 0) {
      return 0.0;
    }
    return ((_idleSheetExtent - _kIdleSheetMin) / span).clamp(0.0, 1.0);
  }

  /// Ограничение частоты кадров при стриме, без влияния на нативный предпросмотр.
  DateTime? _lastStreamFrameAt;

  StreamConnectionQuality _streamQuality = StreamConnectionQuality.high;

  /// Качество текущей сессии после HELLO_OK (эхо запроса телефона).
  int _negotiatedStreamQ = 2;

  /// Подавляет snack-сообщения во время фонового поиска/авто-подключения.
  bool _autoConnecting = false;

  /// Последние успешные подключения (показываются как чипы в листе).
  List<QrConnectConfig> _recentConnections = [];

  /// Фоновый цикл поиска активен, пока не подключились.
  bool _discoveryLoopActive = false;

  /// Флаг: «уже было хотя бы одно успешное подключение в этом запуске
  /// приложения». После первого успеха автоматический discovery-loop
  /// больше не запускается ни при разрыве, ни при сбросе сессии — пользователь
  /// сам решает, переподключаться ли (через QR / список недавних).
  bool _hasConnectedOnce = false;

  final CameraLensDirection _lens = CameraLensDirection.back;

  @override
  void initState() {
    super.initState();
    _client.onDisconnected = _onStreamSocketClosedByHost;
    _client.onServerSession = _onServerSessionFromPc;
    _webrtcClient.onDisconnected = _onStreamSocketClosedByHost;
    unawaited(_initWebRtcPreview());
    unawaited(_loadStreamQualityPref());
    unawaited(_loadRecentConnections());
    _scanner = MobileScannerController(cameraResolution: const Size(640, 480));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _applyImmersiveChrome();
      unawaited(_lockPortraitIdle());
      _startDiscoveryLoop();
    });
  }

  Future<void> _loadStreamQualityPref() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_kStreamQualityPrefKey);
    final q = switch (raw) {
      'low' => StreamConnectionQuality.low,
      'medium' => StreamConnectionQuality.medium,
      'high' => StreamConnectionQuality.high,
      _ => StreamConnectionQuality.high,
    };
    if (mounted) {
      setState(() => _streamQuality = q);
    }
  }

  Future<void> _initWebRtcPreview() async {
    try {
      await _webrtcPreview.initialize();
      if (mounted) {
        setState(() => _webrtcPreviewReady = true);
      }
    } on Object {
      if (mounted) {
        setState(() => _webrtcPreviewReady = false);
      }
    }
  }

  Future<void> _persistStreamQuality(StreamConnectionQuality q) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kStreamQualityPrefKey, switch (q) {
      StreamConnectionQuality.low => 'low',
      StreamConnectionQuality.medium => 'medium',
      StreamConnectionQuality.high => 'high',
    });
  }

  Future<void> _saveConnectionConfig(QrConnectConfig cfg) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kSavedHostKey, cfg.host);
    await p.setString(_kSavedPortKey, '${cfg.port}');
    await p.setString(_kSavedTokenKey, cfg.token);
    if (cfg.mode != null) {
      await p.setString(_kSavedModeKey, cfg.mode!);
    } else {
      await p.remove(_kSavedModeKey);
    }
    if (cfg.signalingPort != null) {
      await p.setString(_kSavedSignalingPortKey, '${cfg.signalingPort}');
    } else {
      await p.remove(_kSavedSignalingPortKey);
    }
  }

  /// Запускает фоновый цикл поиска ПК (если уже запущен — ничего не делает).
  ///
  /// После первого УСПЕШНОГО подключения за время жизни приложения цикл
  /// больше не стартует автоматически. Это сделано осознанно: иначе при
  /// каждом разрыве (закрыли крышку ноута, ПК ушёл в сон, отвалилась сеть)
  /// телефон бесконечно дёргает камеру и пинает discovery, что и раздражает.
  /// Перезапустить цикл можно только перезапуском приложения или вручную
  /// через QR / список недавних подключений.
  void _startDiscoveryLoop() {
    if (_hasConnectedOnce) return;
    if (_discoveryLoopActive) return;
    _discoveryLoopActive = true;
    unawaited(_discoveryLoop());
  }

  void _stopDiscoveryLoop() {
    _discoveryLoopActive = false;
  }

  /// Непрерывно ищет ПК (mDNS / USB) и подключается, пока не установлена трансляция.
  Future<void> _discoveryLoop() async {
    // Небольшая задержка на первый рендер.
    await Future.delayed(const Duration(milliseconds: 400));

    while (mounted && _discoveryLoopActive) {
      // Уже стримим — цикл не нужен, выходим.
      if (_streaming) break;

      // QR-сканер открыт или пользователь вручную подключается — ждём, не мешаем.
      if (_qrFullscreenOpen || _streamStartInFlight) {
        await Future.delayed(const Duration(seconds: 2));
        continue;
      }

      // --- Попытка поиска ---
      _autoConnecting = true;
      if (mounted) setState(() {});

      try {
        // mDNS (WiFi) + HTTP 127.0.0.1 (USB) одновременно, таймаут 5 с.
        QrConnectConfig? cfg = await discoverHost(
          timeout: const Duration(seconds: 5),
        );

        if (cfg != null) {
          // 127.0.0.1 актуален только для USB/ADB — не сохраняем в постоянный конфиг.
          if (!_isLoopback(cfg.host)) {
            unawaited(_saveConnectionConfig(cfg));
          }
        } else {
          // Обнаружение не сработало — берём последний сохранённый конфиг.
          cfg = await _loadSavedConfig();
        }

        if (cfg != null && mounted && !_streaming && !_streamStartInFlight) {
          setState(() {
            _hostCtrl.text = cfg!.host;
            _portCtrl.text = '${cfg.port}';
            _tokenCtrl.text = cfg.token;
            _lastQrConfig = cfg;
          });
          // _autoConnecting остаётся true — подавляет snack-ошибки во время авто-подключения;
          // _streamStartInFlight из _startStreamingIfPossible управляет анимацией «Подключение…».
          await _startStreamingIfPossible();
          if (_streaming) break; // Подключились — выходим из цикла.
        }
      } on Object {
        // Игнорируем все ошибки внутри цикла.
      } finally {
        _autoConnecting = false;
        if (mounted) setState(() {});
      }

      if (!mounted || !_discoveryLoopActive || _streaming) break;

      // Пауза перед следующей попыткой.
      await Future.delayed(const Duration(seconds: 10));
    }

    _discoveryLoopActive = false;
    _autoConnecting = false;
    if (mounted) setState(() {});
  }

  static bool _isLoopback(String host) {
    final h = host.trim().toLowerCase();
    return h == '127.0.0.1' || h == 'localhost' || h == '::1';
  }

  Future<QrConnectConfig?> _loadSavedConfig() async {
    final p = await SharedPreferences.getInstance();
    final host = p.getString(_kSavedHostKey) ?? '';
    final portStr = p.getString(_kSavedPortKey) ?? '';
    final token = p.getString(_kSavedTokenKey) ?? '';
    // Loopback-адрес из прошлой USB-сессии не подходит для WiFi-подключения.
    if (host.isEmpty || portStr.isEmpty || token.isEmpty || _isLoopback(host))
      return null;
    final port = int.tryParse(portStr);
    if (port == null) return null;
    final mode = p.getString(_kSavedModeKey);
    final spStr = p.getString(_kSavedSignalingPortKey);
    final signalingPort = spStr != null ? int.tryParse(spStr) : null;
    return QrConnectConfig(
      host: host,
      port: port,
      token: token,
      mode: mode,
      signalingPort: signalingPort,
    );
  }

  Future<void> _loadRecentConnections() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_kRecentConnectionsKey);
    if (raw == null || raw.isEmpty) return;
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      final parsed = <QrConnectConfig>[];
      for (final item in list) {
        if (item is! Map<String, dynamic>) continue;
        final h = item['h'];
        final t = item['t'];
        final pv = item['p'];
        if (h is! String || t is! String || h.isEmpty || t.isEmpty) continue;
        final port = pv is int ? pv : int.tryParse('$pv');
        if (port == null) continue;
        final sp = item['sp'];
        final n = item['n'];
        parsed.add(
          QrConnectConfig(
            host: h,
            port: port,
            token: t,
            mode: item['m'] is String ? item['m'] as String : null,
            signalingPort: sp is int ? sp : int.tryParse('$sp'),
            name: n is String && n.isNotEmpty ? n : null,
          ),
        );
      }
      if (mounted) setState(() => _recentConnections = parsed);
    } on Object {
      // ignore corrupt data
    }
  }

  Future<void> _saveRecentConnection(QrConnectConfig cfg) async {
    String dedup(QrConnectConfig c) =>
        c.name?.isNotEmpty == true ? c.name! : '${c.host}:${c.port}';
    final key = dedup(cfg);
    final updated = [
      cfg,
      ..._recentConnections.where((c) => dedup(c) != key),
    ].take(_kMaxRecentConnections).toList();
    if (mounted) setState(() => _recentConnections = updated);
    final p = await SharedPreferences.getInstance();
    final encoded = jsonEncode(
      updated
          .map(
            (c) => {
              'h': c.host,
              'p': c.port,
              't': c.token,
              if (c.mode != null) 'm': c.mode,
              if (c.signalingPort != null) 'sp': c.signalingPort,
              if (c.name != null) 'n': c.name,
            },
          )
          .toList(),
    );
    await p.setString(_kRecentConnectionsKey, encoded);
  }

  void _onStreamSocketClosedByHost() {
    if (!mounted || _streamStartInFlight) {
      return;
    }
    unawaited(_handleHostStoppedStreaming());
  }

  /// Разрыв TCP (ПК закрыл приложение, сеть, кабель и т.д.) — главный экран: сканер QR.
  Future<void> _handleHostStoppedStreaming() async {
    if (!mounted) {
      return;
    }
    await _switchToScanner(resetConnection: true);
    if (!mounted) {
      return;
    }
    _snack('Соединение с ПК разорвано.', duration: const Duration(seconds: 4));
    // НЕ возобновляем discovery: после первого подключения переподключаемся
    // только вручную (QR / список недавних). Это решение пользователя.
  }

  void _onServerSessionFromPc(bool live) {
    if (!mounted) {
      return;
    }
    unawaited(_syncStreamLiveFromPc(live));
  }

  /// Реакция на SERVER_SESSION с ПК.
  Future<void> _syncStreamLiveFromPc(bool live) async {
    if (!mounted) {
      return;
    }
    if (!live) {
      await _switchToScanner(resetConnection: true);
      if (mounted) {
        _snack('ПК завершил трансляцию.', duration: const Duration(seconds: 4));
        // Discovery-loop осознанно НЕ перезапускаем — после первого
        // подключения переподключение только вручную.
      }
      return;
    }
    if (_streaming) {
      return;
    }
    if (_mode != _ViewMode.camera ||
        _camera == null ||
        !_camera!.value.isInitialized) {
      return;
    }
    await _enterStreamScreen(webrtc: false);
    _lastStreamFrameAt = null;
    await _attachImageStream();
  }

  Future<void> _attachImageStream() async {
    final controller = _camera!;
    if (controller.value.isStreamingImages) {
      return;
    }
    await controller.startImageStream((CameraImage image) {
      if (!_streaming) {
        return;
      }
      if (_busy) {
        return;
      }
      final now = DateTime.now();
      final last = _lastStreamFrameAt;
      if (last != null &&
          now.difference(last) <
              streamIntervalForNegotiatedStream(_negotiatedStreamQ)) {
        return;
      }
      _lastStreamFrameAt = now;
      _busy = true;
      unawaited(_processFrame(image, controller));
    });
  }

  void _applyImmersiveChrome() {
    if (!mounted || kIsWeb) return;
    // Edge-to-edge: камера под прозрачным статус-баром без чёрной «полосы» от immersive.
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: Colors.transparent,
        systemNavigationBarDividerColor: Colors.transparent,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
    );
  }

  void _restoreChrome() {
    if (kIsWeb) return;
    SystemChrome.setEnabledSystemUIMode(
      SystemUiMode.manual,
      overlays: SystemUiOverlay.values,
    );
    SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle.dark);
  }

  /// Главный экран / ожидание подключения — только портрет.
  Future<void> _lockPortraitIdle() async {
    if (kIsWeb) return;
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
    ]);
  }

  /// Экран трансляции — только альбомная.
  Future<void> _lockStreamLandscape() async {
    if (kIsWeb) return;
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    await Future<void>.delayed(const Duration(milliseconds: 280));
  }

  /// TCP/JPEG: камера должна снимать в альбомной, как экран трансляции.
  Future<void> _ensureCameraLandscapeForTcpStream() async {
    final cableTcp = _isLoopback(_hostCtrl.text.trim());
    if (_camera == null || !_camera!.value.isInitialized) {
      await _openCameraController(cableTcp: cableTcp);
      return;
    }
    try {
      await _camera!.lockCaptureOrientation(DeviceOrientation.landscapeRight);
    } on Object {
      // ignore
    }
    await Future<void>.delayed(const Duration(milliseconds: 220));
    if (!mounted) return;
    final v = _camera!.value;
    if (_cameraValueIsLandscape(v)) return;

    await _camera?.stopImageStream().catchError((_) {});
    await _disposeCamera();
    await _androidGap();
    if (!mounted) return;
    await _openCameraController(cableTcp: cableTcp);
  }

  /// Открыть полноэкранную трансляцию (поворот + UI).
  Future<void> _enterStreamScreen({required bool webrtc}) async {
    await _lockStreamLandscape();
    if (!mounted) return;
    if (!webrtc) {
      await _ensureCameraLandscapeForTcpStream();
      if (!mounted) return;
    }
    setState(() {
      _streaming = true;
      _streamViaWebRtc = webrtc;
      _mode = _ViewMode.camera;
      _suppressCameraPreview = false;
      _idleCenterQrPrimed = false;
      _idleSheetExtent = _kIdleSheetMin;
      _autoConnecting = false;
      _streamDragX = 0;
      _streamDismissing = false;
    });
  }

  /// Закрыть экран трансляции — вернуть портрет.
  Future<void> _exitStreamScreen() async {
    _streaming = false;
    _streamViaWebRtc = false;
    await _lockPortraitIdle();
  }

  bool _parseConnectConfigValid() {
    final host = _hostCtrl.text.trim();
    final port = int.tryParse(_portCtrl.text.trim());
    final token = _tokenCtrl.text.trim();
    return host.isNotEmpty && port != null && token.isNotEmpty;
  }

  void _snack(
    String message, {
    Duration duration = const Duration(seconds: 3),
  }) {
    if (!mounted) return;
    if (_autoConnecting) return;
    final bottom = MediaQuery.paddingOf(context).bottom + 96;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: Text(message, style: const TextStyle(height: 1.35)),
        duration: duration,
        behavior: SnackBarBehavior.floating,
        margin: EdgeInsets.fromLTRB(16, 0, 16, bottom),
      ),
    );
  }

  /// Подсказка при Connection refused на localhost (USB без проброса порта и т.п.).
  /// 172.17–172.22 на Windows часто vEthernet Docker/WSL — с телефона недоступен.
  static String? _lanHostLooksLikeVirtual172(String host) {
    final parts = host.trim().split('.');
    if (parts.length != 4) return null;
    final a = int.tryParse(parts[0]);
    final b = int.tryParse(parts[1]);
    if (a == null || b == null || a != 172) return null;
    if (b < 17 || b > 22) return null;
    return 'В хосте похоже адрес Docker/WSL (172.$b.x), с телефона он обычно не '
        'достижим. Обновите десктоп Smart Cam и отсканируйте QR снова — там должен '
        'быть IP Wi‑Fi (часто 192.168…).';
  }

  String _formatConnectFailure(Object e, String host, int port) {
    final h = host.trim().toLowerCase();
    final isLocal = h == '127.0.0.1' || h == 'localhost' || h == '::1';
    final base = 'Не удалось подключиться: $e';
    final es = e.toString();
    final looksLikeTimeout =
        es.contains('timed out') ||
        es.contains('Timeout') ||
        es.contains('errno = 110') ||
        es.contains('ETIMEDOUT');
    if (!isLocal) {
      final v172 = _lanHostLooksLikeVirtual172(host);
      var tail =
          'Wi‑Fi: телефон и ПК в одной сети. После смены Cable/Wi‑Fi на ПК '
          'отсканируйте QR заново.';
      if (looksLikeTimeout) {
        tail =
            '$tail\n\n'
            'При таймауте чаще всего блокирует брандмауэр Windows: на ПК в Smart Cam '
            'откройте настройки → «Разрешить порт в брандмауэре…» (порт $port) и '
            'подтвердите UAC. Проверьте также, что на роутере выключена изоляция '
            'клиентов (guest / AP isolation).';
      }
      if (v172 != null) {
        return '$base\n\n$v172\n\n$tail';
      }
      return '$base\n\n$tail';
    }
    return '$base\n\n'
        'Если на ПК режим Wi‑Fi — отсканируйте QR ещё раз: там должен быть IP '
        'компьютера в LAN, а не 127.0.0.1.\n\n'
        'Для USB (Cable): на ПК Smart Cam в режиме Cable, adb reverse; на телефоне '
        'отладка по USB и кабель; хост 127.0.0.1, порт $port.';
  }

  @override
  void dispose() {
    _stopDiscoveryLoop();
    unawaited(_lockPortraitIdle());
    _restoreChrome();
    _hostCtrl.dispose();
    _portCtrl.dispose();
    _tokenCtrl.dispose();
    unawaited(_disposeScanner());
    unawaited(_disposeQrOverlayOnly());
    unawaited(_disposeCamera());
    _webrtcPreview.srcObject = null;
    unawaited(_webrtcPreview.dispose());
    unawaited(_client.disconnect());
    unawaited(_webrtcClient.disconnect());
    unawaited(_jpegEncoder.dispose());
    super.dispose();
  }

  Future<void> _disposeScanner() async {
    final s = _scanner;
    _scanner = null;
    if (s != null) await s.dispose();
  }

  Future<void> _disposeQrOverlayOnly() async {
    final c = _qrOverlayOnlyController;
    _qrOverlayOnlyController = null;
    if (c != null) await c.dispose();
  }

  Future<void> _disposeCamera() async {
    await _camera?.stopImageStream().catchError((_) {});
    await _camera?.dispose();
    _camera = null;
  }

  Future<void> _androidGap() async {
    if (defaultTargetPlatform == TargetPlatform.android) {
      await Future<void>.delayed(const Duration(milliseconds: 550));
    }
  }

  Future<void> _startStreamingIfPossible() async {
    if (_streamStartInFlight) {
      return;
    }
    if (!_parseConnectConfigValid()) {
      return;
    }
    if (_streaming) {
      return;
    }
    _streamStartInFlight = true;
    if (mounted) {
      setState(() {});
    }
    try {
      final cfg = _lastQrConfig;
      final host = _hostCtrl.text.trim();
      final port = int.tryParse(_portCtrl.text.trim()) ?? 0;
      final token = _tokenCtrl.text.trim();
      // QR/обнаружение могло не сообщить sp — но десктоп держит сигналинг
      // на streamPort+1. Эвристика даёт WebRTC даже для «старых» подключений.
      final hintedSp = cfg?.signalingPort;
      final fallbackSp = port > 0 ? port + _kSignalingPortOffsetFallback : null;
      final signalingPort = hintedSp ?? fallbackSp;
      // Не блокируем WebRTC по cfg.mode=='tcp': старые QR/чипы могли быть
      // сгенерированы ПК в режиме TCP, но новый ПК уже поднимает aiortc на
      // том же `port+1`. Если сигналинг недоступен — упадём в catch и
      // прозрачно перейдём на TCP/JPEG.
      final webrtcHost = () {
        final lip = cfg?.lanHost;
        if (lip != null && lip.isNotEmpty && _isLoopback(host)) {
          return lip;
        }
        return host;
      }();
      final isLoopback = _isLoopback(webrtcHost);
      final canTryWebRtc =
          !_forceTcpTransport &&
          !isLoopback &&
          webrtcHost.isNotEmpty &&
          token.isNotEmpty &&
          signalingPort != null &&
          signalingPort > 0;

      if (canTryWebRtc) {
        final webRtcCfg = QrConnectConfig(
          host: webrtcHost,
          port: port,
          token: token,
          mode: 'webrtc',
          signalingPort: signalingPort,
          name: cfg?.name,
          lanHost: cfg?.lanHost,
        );
        final ok = await _startWebRtcStream(webRtcCfg);
        if (ok) {
          if (mounted) {
            _snack(
              'Wi‑Fi: WebRTC 720p30 (низкая задержка)',
              duration: const Duration(seconds: 3),
            );
          }
          return;
        }
        if (mounted) {
          _snack(
            'WebRTC не подключился — запасной TCP/JPEG (ниже качество). '
            'Проверьте брандмауэр и что телефон и ПК в одной Wi‑Fi.',
            duration: const Duration(seconds: 8),
          );
        }
      } else if (isLoopback && mounted && !_forceTcpTransport) {
        _snack(
          'USB: трансляция по TCP (WebRTC по кабелю без UDP не поддерживается).',
          duration: const Duration(seconds: 4),
        );
      }
      _streamViaWebRtc = false;
      if (_mode == _ViewMode.scanner) {
        await _switchToCamera();
        if (!mounted) {
          return;
        }
        if (_camera == null || !_camera!.value.isInitialized) {
          return;
        }
      }
      await _startStream();
    } finally {
      _streamStartInFlight = false;
      if (mounted) {
        setState(() {});
      }
    }
  }

  /// Поднимает WebRTC-поток (аппаратное H.264/VP8 кодирование на телефоне,
  /// аппаратное декодирование на ПК через aiortc).
  ///
  /// Возвращает `true`, если соединение установлено. На любых ошибках —
  /// `false` без сайд-эффектов на UI; вызывающая сторона решает, делать ли
  /// fallback на TCP/JPEG. Это и есть тот самый «способ передачи», после
  /// перевода на который видео идёт стабильно 30 fps с низкой задержкой даже
  /// по Wi-Fi, не говоря о проводе.
  Future<bool> _startWebRtcStream(QrConnectConfig cfg) async {
    final cam = await Permission.camera.request();
    if (!cam.isGranted) {
      if (mounted) {
        _snack('Camera permission denied.');
      }
      return false;
    }
    if (_mode == _ViewMode.scanner) {
      await _disposeScanner();
      await _androidGap();
      if (!mounted) return false;
    }
    final signalingPort = cfg.signalingPort;
    if (cfg.host.isEmpty || cfg.token.isEmpty || signalingPort == null) {
      return false;
    }
    try {
      if (!mounted) return false;
      await _enterStreamScreen(webrtc: true);
      await _webrtcClient.connect(
        host: cfg.host,
        signalingPort: signalingPort,
        token: cfg.token,
        highQuality: !_isLoopback(cfg.host),
      );
      _webrtcPreview.srcObject = _webrtcClient.localStream;
      if (!mounted) {
        await _webrtcClient.disconnect();
        _webrtcPreview.srcObject = null;
        await _exitStreamScreen();
        if (mounted) setState(() {});
        return false;
      }
      _hasConnectedOnce = true;
      _stopDiscoveryLoop();
      unawaited(_saveRecentConnection(cfg));
      return true;
    } on Object {
      _webrtcPreview.srcObject = null;
      try {
        await _webrtcClient.disconnect();
      } on Object {
        // ignore
      }
      await _exitStreamScreen();
      if (mounted) setState(() {});
      await _androidGap();
      return false;
    }
  }

  Future<void> _switchToCamera() async {
    final cam = await Permission.camera.request();
    if (!cam.isGranted) {
      if (mounted) {
        _snack('Camera permission denied.');
      }
      return;
    }

    if (mounted) {
      setState(() => _suppressCameraPreview = true);
    }
    await _disposeScanner();
    await _androidGap();
    if (!mounted) return;

    final opened = await _openCameraController(
      cableTcp: _isLoopback(_hostCtrl.text.trim()),
    );
    if (!mounted) return;
    if (!opened) {
      if (mounted) {
        setState(() {
          _suppressCameraPreview = false;
          _scanner = MobileScannerController(
            cameraResolution: const Size(640, 480),
          );
          _mode = _ViewMode.scanner;
        });
      }
      return;
    }

    setState(() {
      _suppressCameraPreview = false;
      _mode = _ViewMode.camera;
      _idleCenterQrPrimed = false;
    });
  }

  Future<void> _switchToScanner({bool resetConnection = false}) async {
    if (mounted) {
      setState(() => _suppressCameraPreview = true);
    }
    if (_streaming) {
      await _stopStream();
    }
    await _client.disconnect();
    await _webrtcClient.disconnect();
    await _disposeCamera();
    await _androidGap();
    if (!mounted) return;

    setState(() {
      _suppressCameraPreview = false;
      _streamDragX = 0;
      _streamDismissing = false;
      _scanner = MobileScannerController(
        cameraResolution: const Size(640, 480),
      );
      _mode = _ViewMode.scanner;
      _idleCenterQrPrimed = false;
      if (resetConnection) {
        _hostCtrl.clear();
        _portCtrl.text = '17777';
        _tokenCtrl.clear();
        _lastQrConfig = null;
      }
      _streamViaWebRtc = false;
    });
  }

  Future<bool> _openCameraController({bool cableTcp = false}) async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      _snack('No camera found.');
      return false;
    }

    CameraDescription pick() {
      try {
        return cameras.firstWhere((c) => c.lensDirection == _lens);
      } on Object {
        return cameras.first;
      }
    }

    Future<CameraController?> openOnce() async {
      final controller = CameraController(
        pick(),
        // TCP/JPEG: USB — medium (~480p); Wi‑Fi fallback — high (~720p+).
        cableTcp ? ResolutionPreset.medium : ResolutionPreset.veryHigh,
        enableAudio: false,
        fps: 30,
        imageFormatGroup: defaultTargetPlatform == TargetPlatform.iOS
            ? ImageFormatGroup.bgra8888
            : ImageFormatGroup.yuv420,
      );
      await controller.initialize();
      try {
        // TCP-трансляция всегда в альбомной (экран тоже landscape).
        await controller.lockCaptureOrientation(
          DeviceOrientation.landscapeRight,
        );
      } on Object {
        // Не на всех устройствах / эмуляторах доступно.
      }
      return controller;
    }

    CameraController? controller;
    try {
      controller = await openOnce();
    } on Object catch (e) {
      if (defaultTargetPlatform == TargetPlatform.android) {
        await Future<void>.delayed(const Duration(milliseconds: 450));
        if (!mounted) return false;
        try {
          controller = await openOnce();
        } on Object catch (e2) {
          _snack('Camera error: $e2');
          return false;
        }
      } else {
        _snack('Camera error: $e');
        return false;
      }
    }

    if (!mounted) {
      await controller?.dispose();
      return false;
    }
    _camera = controller;
    return true;
  }

  Future<void> _stopStream() async {
    _lastStreamFrameAt = null;
    if (_streamViaWebRtc) {
      await _webrtcClient.disconnect();
      _webrtcPreview.srcObject = null;
    } else {
      await _camera?.stopImageStream().catchError((_) {});
      try {
        await _client.sendClientSession(false);
      } on Object catch (_) {}
    }
    await _exitStreamScreen();
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _startStream() async {
    _streamViaWebRtc = false;
    final host = _hostCtrl.text.trim();
    final cableTcp = _isLoopback(host);
    // USB — минимум; Wi‑Fi fallback — высокое качество JPEG.
    _negotiatedStreamQ = cableTcp ? 0 : 2;
    if (_camera == null || !_camera!.value.isInitialized) {
      _snack('Camera not ready.');
      return;
    }
    if (!_cameraValueIsLandscape(_camera!.value)) {
      await _ensureCameraLandscapeForTcpStream();
      if (!mounted ||
          _camera == null ||
          !_camera!.value.isInitialized) {
        _snack('Camera not ready.');
        return;
      }
    }

    final port = int.tryParse(_portCtrl.text.trim());
    final token = _tokenCtrl.text.trim();
    if (host.isEmpty || port == null || token.isEmpty) {
      return;
    }

    if (!_client.isConnected) {
      var frameRotateK = 0;
      final ps = _camera!.value.previewSize;
      if (ps != null) {
        frameRotateK = frameRotateKForTcpHello(
          ps.width.round(),
          ps.height.round(),
          cableLoopback: cableTcp,
        );
      } else if (cableTcp) {
        frameRotateK = 2;
      }
      try {
        final hello = await _client.connect(
          host,
          port,
          token,
          clientStreamQuality: cableTcp ? 0 : 2,
          frameRotateK: frameRotateK,
        );
        if (!mounted) {
          return;
        }
        setState(() {
          _negotiatedStreamQ = hello.qualityIndex;
        });
      } on ProtocolException catch (e) {
        _snack('Auth / protocol error: $e');
        return;
      } on Object catch (e) {
        _snack(
          _formatConnectFailure(e, host, port),
          duration: const Duration(seconds: 12),
        );
        return;
      }
    }

    if (!mounted) {
      return;
    }
    await _enterStreamScreen(webrtc: false);
    _hasConnectedOnce = true;
    _stopDiscoveryLoop();
    _lastStreamFrameAt = null;
    // Сохраняем успешное подключение в список недавних.
    final cfg = _lastQrConfig;
    if (cfg != null) unawaited(_saveRecentConnection(cfg));

    await _attachImageStream();
    try {
      await _client.sendClientSession(true);
    } on Object catch (e) {
      await _camera?.stopImageStream().catchError((_) {});
      await _exitStreamScreen();
      if (mounted) {
        setState(() {});
        _snack('Stream error: $e');
      }
    }
  }

  Future<void> _processFrame(
    CameraImage image,
    CameraController controller,
  ) async {
    try {
      if (!_streaming || !controller.value.isInitialized) return;
      final mirrorFront =
          controller.description.lensDirection == CameraLensDirection.front;
      final req = _frameToEncodeRequest(
        image,
        quality: jpegQualityForNegotiatedStream(_negotiatedStreamQ),
        mirror: mirrorFront,
      );
      if (req == null) return;
      final jpeg = await _jpegEncoder.encode(req);
      if (jpeg != null && _streaming) {
        _client.sendFrame(image.width, image.height, jpeg);
      }
    } on Object catch (e) {
      if (mounted) {
        unawaited(_stopStream());
        _snack('Stream error: $e');
      }
    } finally {
      _busy = false;
    }
  }

  /// Пакует `CameraImage` в [JpegEncodeRequest] для отправки в воркер-изолят.
  /// Возвращает null если формат не поддерживается.
  bool get _tcpCableRotate180 =>
      _streaming &&
      !_streamViaWebRtc &&
      _isLoopback(_hostCtrl.text.trim());

  JpegEncodeRequest? _frameToEncodeRequest(
    CameraImage image, {
    required int quality,
    required bool mirror,
  }) {
    final group = image.format.group;
    if (group == ImageFormatGroup.bgra8888) {
      final plane = image.planes[0];
      return JpegEncodeRequest(
        width: image.width,
        height: image.height,
        format: FrameFormat.bgra,
        yBytes: plane.bytes,
        yRow: plane.bytesPerRow,
        bgraRow: plane.bytesPerRow,
        quality: quality,
        mirrorHorizontal: mirror,
      );
    }
    if (group == ImageFormatGroup.yuv420) {
      final planes = image.planes;
      if (planes.length == 3) {
        return JpegEncodeRequest(
          width: image.width,
          height: image.height,
          format: FrameFormat.yuv420Planar,
          yBytes: planes[0].bytes,
          uBytes: planes[1].bytes,
          vBytes: planes[2].bytes,
          yRow: planes[0].bytesPerRow,
          uRow: planes[1].bytesPerRow,
          vRow: planes[2].bytesPerRow,
          uPixel: planes[1].bytesPerPixel ?? 1,
          vPixel: planes[2].bytesPerPixel ?? 1,
          quality: quality,
          mirrorHorizontal: mirror,
        );
      }
      if (planes.length == 2) {
        return JpegEncodeRequest(
          width: image.width,
          height: image.height,
          format: FrameFormat.nv21,
          yBytes: planes[0].bytes,
          uvBytes: planes[1].bytes,
          yRow: planes[0].bytesPerRow,
          uvRow: planes[1].bytesPerRow,
          quality: quality,
          mirrorHorizontal: mirror,
        );
      }
    }
    return null;
  }

  static const _white = Colors.white;

  InputDecoration _idleConnFieldDeco(String hint) {
    return InputDecoration(
      hintText: hint,
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
      filled: true,
      fillColor: Colors.transparent,
      hintStyle: TextStyle(color: _white.withValues(alpha: 0.55), fontSize: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(20),
        borderSide: BorderSide(color: _white.withValues(alpha: 0.9)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(20),
        borderSide: BorderSide(color: _white.withValues(alpha: 0.9)),
      ),
      focusedBorder: const OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(20)),
        borderSide: BorderSide(color: _white, width: 1.4),
      ),
    );
  }

  Widget _buildQualitySegment(StreamConnectionQuality q, String label) {
    final selected = _streamQuality == q;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          if (_streamQuality == q) return;
          setState(() => _streamQuality = q);
          unawaited(_persistStreamQuality(q));
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOutCubic,
          margin: const EdgeInsets.all(4),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
          decoration: BoxDecoration(
            color: selected ? _white : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: selected ? kAppScreenBackground : _white,
              fontWeight: FontWeight.w600,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildQualitySwitch() {
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: _white),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        children: [
          _buildQualitySegment(StreamConnectionQuality.low, 'Низкое'),
          _buildQualitySegment(StreamConnectionQuality.medium, 'Среднее'),
          _buildQualitySegment(StreamConnectionQuality.high, 'Высокое'),
        ],
      ),
    );
  }

  Widget _buildIdleConnectionSheetContent(ScrollController scrollController) {
    if (!_showIdleConnectionChrome) {
      return const ColoredBox(color: Colors.transparent);
    }

    final pulled = _idleSheetExtent > _kIdlePullConnectLabel;
    final showHelper =
        (_idleSheetExtent > 0.13 || _streamStartInFlight) &&
        !(_idleCenterQrPrimed && !pulled && !_streamStartInFlight);

    return ColoredBox(
      color: Colors.transparent,
      child: CustomScrollView(
        controller: scrollController,
        physics: const ClampingScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 6, 20, 8),
              child: Builder(
                builder: (context) {
                  final screenH = MediaQuery.sizeOf(context).height;
                  final visibleSheetH = screenH * _idleSheetExtent;
                  final handleH =
                      _kIdleHandleBlockBase +
                      (showHelper ? _kIdleHandleHelperExtra : 0);
                  // Пока не показан блок с формой, заполняем видимую высоту листа, чтобы
                  // соседний sliver не просвечивал (в т.ч. при промежуточном pull).
                  final topFill = showHelper
                      ? 0.0
                      : (visibleSheetH - handleH).clamp(0.0, screenH);
                  return Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const _PulsingPullHintChevron(),
                      const SizedBox(height: 2),
                      const _ConnectingTitle(),
                      if (showHelper) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Если не удаётся подключиться, отсканируйте QR, '
                          'нажав на кнопку выше',
                          textAlign: TextAlign.center,
                          maxLines: 2,
                          style: TextStyle(
                            color: _white.withValues(alpha: 0.9),
                            fontSize: 11,
                            fontWeight: FontWeight.w500,
                            height: 1.3,
                          ),
                        ),
                      ],
                      if (topFill > 0) SizedBox(height: topFill),
                    ],
                  );
                },
              ),
            ),
          ),
          if (showHelper)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Качество',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: _white,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 10),
                    _buildQualitySwitch(),
                    const SizedBox(height: 18),
                    const Text(
                      'Детали подключения',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: _white,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: SizedBox(
                            height: 48,
                            child: TextField(
                              controller: _hostCtrl,
                              style: const TextStyle(
                                color: _white,
                                fontSize: 12,
                              ),
                              decoration: _idleConnFieldDeco('Хост'),
                              keyboardType: TextInputType.url,
                              textInputAction: TextInputAction.next,
                              autocorrect: false,
                            ),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: SizedBox(
                            height: 48,
                            child: TextField(
                              controller: _portCtrl,
                              style: const TextStyle(
                                color: _white,
                                fontSize: 12,
                              ),
                              decoration: _idleConnFieldDeco('# Порт'),
                              keyboardType: TextInputType.number,
                              textInputAction: TextInputAction.next,
                            ),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: SizedBox(
                            height: 48,
                            child: TextField(
                              controller: _tokenCtrl,
                              style: const TextStyle(
                                color: _white,
                                fontSize: 12,
                              ),
                              decoration: _idleConnFieldDeco('Токен'),
                              obscureText: true,
                              autocorrect: false,
                              textInputAction: TextInputAction.done,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (_recentConnections.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: Text(
                          'Недавние',
                          style: TextStyle(
                            color: _white.withValues(alpha: 0.7),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.4,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _recentConnections
                            .map(_buildConnectionChip)
                            .toList(),
                      ),
                    ],
                    SizedBox(height: 12 + MediaQuery.paddingOf(context).bottom),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildConnectionChip(QrConnectConfig cfg) {
    return GestureDetector(
      onTap: () {
        setState(() {
          _hostCtrl.text = cfg.host;
          _portCtrl.text = '${cfg.port}';
          _tokenCtrl.text = cfg.token;
          _lastQrConfig = cfg;
        });
        unawaited(_startStreamingIfPossible());
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: Colors.white.withValues(alpha: 0.45)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.computer_rounded,
              size: 14,
              color: Colors.white.withValues(alpha: 0.8),
            ),
            const SizedBox(width: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 160),
              child: Text(
                cfg.displayName,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Со экрана живого стрима — в сканер QR и сброс host/port/token.
  Future<void> _animateStreamDismiss(double screenW) async {
    if (_streamDismissing) return;
    setState(() => _streamDismissing = true);
    const step = Duration(milliseconds: 14);
    while (mounted && _streamDragX < screenW * 0.98) {
      setState(() {
        _streamDragX += (screenW * 1.02 - _streamDragX) * 0.32;
        if (_streamDragX > screenW) _streamDragX = screenW;
      });
      await Future<void>.delayed(step);
    }
    if (mounted) {
      _streamDragX = 0;
      _streamDismissing = false;
      await _switchToScanner(resetConnection: true);
    }
  }

  void _onQrScanDragXChanged(double x) {
    if (!mounted) {
      return;
    }
    setState(() => _qrBackdropDragX = x);
  }

  Future<void> _closeQrFullscreen() async {
    if (!_qrFullscreenOpen) return;
    final extra = _qrOverlayOnlyController;
    _qrOverlayOnlyController = null;
    if (mounted) {
      setState(() {
        _qrFullscreenOpen = false;
        _idleCenterQrPrimed = false;
        _qrBackdropDragX = 0;
      });
    }
    if (extra != null) {
      await extra.dispose();
    }
  }

  Future<void> _onQrFullscreenDecoded(QrConnectConfig cfg) async {
    if (!mounted) return;
    final extra = _qrOverlayOnlyController;
    _qrOverlayOnlyController = null;
    setState(() {
      _qrFullscreenOpen = false;
      _qrBackdropDragX = 0;
      _hostCtrl.text = cfg.host;
      _portCtrl.text = '${cfg.port}';
      _tokenCtrl.text = cfg.token;
      _lastQrConfig = cfg;
    });
    if (extra != null) {
      await extra.dispose();
    }
    if (!mounted) return;
    HapticFeedback.mediumImpact();
    unawaited(_saveConnectionConfig(cfg));
    await _startStreamingIfPossible();
  }

  Future<void> _openFullScreenScanner() async {
    if (_qrFullscreenOpen) return;
    if (_scanner == null) {
      _qrOverlayOnlyController = MobileScannerController(
        cameraResolution: const Size(640, 480),
      );
    }
    if (!mounted) return;
    setState(() {
      _qrFullscreenOpen = true;
      _idleCenterQrPrimed = false;
      _qrBackdropDragX = 0;
    });
  }

  void _onIdleHeroCenterTap() {
    if (_qrFullscreenOpen || _streamStartInFlight) {
      return;
    }
    // Лист потянут вверх — иконка уже QR; одно нажатие открывает сканер.
    final sheetPulled = _idlePullProgress > 0.001;
    if (!(_idleCenterQrPrimed || sheetPulled)) {
      HapticFeedback.selectionClick();
      setState(() => _idleCenterQrPrimed = true);
      return;
    }
    HapticFeedback.lightImpact();
    unawaited(_openFullScreenScanner());
  }

  Widget _buildDraggableIdleSheet() {
    return NotificationListener<DraggableScrollableNotification>(
      onNotification: (n) {
        if ((n.extent - _idleSheetExtent).abs() > 0.002) {
          setState(() => _idleSheetExtent = n.extent);
        }
        return false;
      },
      child: DraggableScrollableSheet(
        minChildSize: _kIdleSheetMin,
        maxChildSize: _kIdleSheetMax,
        initialChildSize: _kIdleSheetMin,
        snap: true,
        snapSizes: const <double>[_kIdleSheetMin, _kIdleSheetMax],
        builder: (context, scrollController) {
          return _buildIdleConnectionSheetContent(scrollController);
        },
      ),
    );
  }

  /// Стрелка «назад» поверх полноэкранного видео (под статус-баром).
  Widget _buildStreamBackButton(double screenW) {
    return IconButton(
      onPressed: () {
        if (_qrFullscreenOpen || _streamDismissing) return;
        HapticFeedback.lightImpact();
        unawaited(_animateStreamDismiss(screenW));
      },
      style: IconButton.styleFrom(
        backgroundColor: Colors.transparent,
        shadowColor: Colors.transparent,
        foregroundColor: Colors.white,
        padding: EdgeInsets.zero,
        minimumSize: const Size(44, 44),
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
      icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 26),
    );
  }

  Widget _buildStreamCard({
    required double screenW,
    required double cornerR,
    required Widget child,
  }) {
    final rounded = _streamDragX > 0 || _streamDismissing;
    return Transform.translate(
      offset: Offset(_streamDragX, 0),
      child: Material(
        elevation: _streamDragX > 0 ? 10 : 0,
        shadowColor: Colors.black54,
        clipBehavior: rounded ? Clip.antiAlias : Clip.none,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(
            Radius.circular(rounded ? cornerR : 0),
          ),
        ),
        child: GestureDetector(
          behavior: HitTestBehavior.translucent,
          onHorizontalDragUpdate: (d) {
            if (_streamDismissing) return;
            setState(() {
              _streamDragX = (_streamDragX + d.delta.dx).clamp(0.0, screenW);
            });
          },
          onHorizontalDragEnd: (d) {
            if (_streamDismissing) return;
            final v = d.primaryVelocity ?? 0;
            if (_streamDragX > screenW * 0.18 || v > 550) {
              unawaited(_animateStreamDismiss(screenW));
            } else {
              setState(() => _streamDragX = 0);
            }
          },
          onHorizontalDragCancel: () {
            if (_streamDismissing || _streamDragX == 0) return;
            setState(() => _streamDragX = 0);
          },
          child: child,
        ),
      ),
    );
  }

  Widget _buildIdleHero() {
    final showPullSheet = _showIdleConnectionChrome &&
        _mode == _ViewMode.scanner &&
        _scanner != null &&
        !_qrFullscreenOpen;
    return _BrandIdleHero(
      centerShowsQrIcon: _idleCenterQrPrimed || _idlePullProgress > 0.001,
      onCenterTap: _onIdleHeroCenterTap,
      pullProgress: _idlePullProgress,
      idlePullSheet: showPullSheet ? _buildDraggableIdleSheet() : null,
    );
  }

  /// Подпись между круглыми кнопками: полноэкранный QR — EN; главный экран — подсказка про QR; при подключении — заголовок с точками.
  Widget _buildBottomBarCenter() {
    if (_qrFullscreenOpen) {
      return Text(
        'Point at the QR on your computer app',
        textAlign: TextAlign.center,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: Colors.white.withValues(alpha: 0.92),
          fontSize: 13,
          fontWeight: FontWeight.w600,
          shadows: const [Shadow(blurRadius: 6, color: Colors.black54)],
        ),
      );
    }
    if (_streamStartInFlight && !_streaming) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const _ConnectingTitle(),
          const SizedBox(height: 4),
          Text(
            'Если не удаётся подключиться, отсканируйте QR',
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.82),
              fontSize: 11,
              fontWeight: FontWeight.w500,
              height: 1.25,
            ),
          ),
        ],
      );
    }
    if (_autoConnecting) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const _ConnectingTitle(title: 'Поиск ПК'),
          const SizedBox(height: 4),
          Text(
            'Или отсканируйте QR вручную',
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.72),
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      );
    }
    if (_streaming) {
      return const SizedBox.shrink();
    }
    if (_idleCenterQrPrimed) {
      return Text(
        'Нажмите на иконку сканера ещё раз',
        textAlign: TextAlign.center,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: Colors.white.withValues(alpha: 0.92),
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      );
    }
    return Text(
      'Если не удаётся подключиться, отсканируйте QR',
      textAlign: TextAlign.center,
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        color: Colors.white.withValues(alpha: 0.92),
        fontSize: 13,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  Widget _buildCameraFill(CameraController c) {
    if (!c.value.isInitialized) {
      return const ColoredBox(color: kAppScreenBackground);
    }
    final mirrorPreview =
        c.description.lensDirection == CameraLensDirection.front;
    return ColoredBox(
      color: kAppScreenBackground,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final w = constraints.maxWidth;
          final h = constraints.maxHeight;
          if (w <= 0 || h <= 0) {
            return const SizedBox.expand();
          }
          final ar = c.value.aspectRatio;
          if (!(ar > 0 && ar.isFinite)) {
            return const Center(
              child: CircularProgressIndicator(color: Colors.white54),
            );
          }
          // Как у [CameraPreview]: в портрете aspectRatio виджета = 1/ar, не ar — иначе растяжение.
          final displayAspectRatio = _cameraValueIsLandscape(c.value)
              ? ar
              : 1 / ar;
          final childW = w;
          final childH = childW / displayAspectRatio;
          // Заполняет экран как на ПК-превью: cover — обрезка по краям, без чёрных полей.
          return ClipRect(
            child: SizedBox(
              width: w,
              height: h,
              child: FittedBox(
                fit: BoxFit.cover,
                clipBehavior: Clip.hardEdge,
                alignment: Alignment.center,
                child: SizedBox(
                  width: childW,
                  height: childH,
                  child: Transform.flip(
                    flipX: mirrorPreview,
                    child: _tcpCableRotate180
                        ? Transform.rotate(
                            angle: math.pi,
                            child: CameraPreview(c),
                          )
                        : CameraPreview(c),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final darkChrome = _mode == _ViewMode.scanner || _mode == _ViewMode.camera;

    final showIdlePullSheet =
        _mode == _ViewMode.scanner && _scanner != null && !_qrFullscreenOpen;

    // Панель скрыта на экране трансляции и во время установки соединения.
    final showBottomChrome =
        !showIdlePullSheet &&
        _showIdleConnectionChrome &&
        !_discoveryLoopActive;
    final qrLayerOpen =
        _qrFullscreenOpen &&
        (_scanner != null || _qrOverlayOnlyController != null);
    final screenW = MediaQuery.sizeOf(context).width;
    final cornerR = qrScanDisplayCornerRadius(context);
    final qrBackdropOffsetX = qrLayerOpen
        ? -0.3 * (screenW - _qrBackdropDragX.clamp(0.0, screenW))
        : 0.0;
    // Параллакс главного экрана при свайпе трансляции.
    final streamParallaxX = (_streaming && !qrLayerOpen)
        ? -0.3 * (screenW - _streamDragX.clamp(0.0, screenW))
        : 0.0;
    final backdropOffsetX = qrLayerOpen ? qrBackdropOffsetX : streamParallaxX;
    final Positioned? bottomChrome = showBottomChrome
        ? Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SafeArea(
              top: false,
              maintainBottomViewPadding: true,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const SizedBox(width: 48, height: 48),
                    Expanded(
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                          child: _buildBottomBarCenter(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 48, height: 48),
                  ],
                ),
              ),
            ),
          )
        : null;

    return PopScope(
      canPop: !_qrFullscreenOpen,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _qrFullscreenOpen) {
          unawaited(_closeQrFullscreen());
        }
      },
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: darkChrome
              ? Brightness.light
              : Brightness.dark,
          systemNavigationBarColor: Colors.transparent,
          systemNavigationBarDividerColor: Colors.transparent,
          systemNavigationBarIconBrightness: darkChrome
              ? Brightness.light
              : Brightness.dark,
        ),
        child: Scaffold(
          key: _scaffoldKey,
          backgroundColor: kAppScreenBackground,
          // Чтобы строка host/port/token в DraggableScrollableSheet оставалась над клавиатурой.
          resizeToAvoidBottomInset: true,
          extendBody: true,
          body: MediaQuery.removePadding(
            context: context,
            removeTop: true,
            child: Stack(
              fit: StackFit.expand,
              clipBehavior: Clip.none,
              children: [
                // Главный экран — всегда на заднем плане (виден при свайпе трансляции).
                Transform.translate(
                  offset: Offset(backdropOffsetX, 0),
                  child: _buildIdleHero(),
                ),

                // Карточка трансляции (JPEG/камера) — свайп вправо → назад.
                if (_streaming &&
                    !_streamViaWebRtc &&
                    !_suppressCameraPreview &&
                    _mode == _ViewMode.camera &&
                    _camera != null &&
                    _camera!.value.isInitialized)
                  _buildStreamCard(
                    screenW: screenW,
                    cornerR: cornerR,
                    child: _buildCameraFill(_camera!),
                  ),

                // Карточка трансляции (WebRTC) — свайп вправо → назад.
                if (_streaming && _streamViaWebRtc && _mode == _ViewMode.camera)
                  _buildStreamCard(
                    screenW: screenW,
                    cornerR: cornerR,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        if (_webrtcPreviewReady &&
                            _webrtcPreview.srcObject != null)
                          rtc.RTCVideoView(
                            _webrtcPreview,
                            objectFit: rtc
                                .RTCVideoViewObjectFit
                                .RTCVideoViewObjectFitCover,
                            mirror: false,
                          )
                        else
                          const ColoredBox(color: kAppScreenBackground),
                        Positioned(
                          top:
                              MediaQuery.paddingOf(context).top +
                              _kStreamOverlayTopExtra,
                          right: 16,
                          child: DecoratedBox(
                              decoration: BoxDecoration(
                                color: Color(0x66000000),
                                borderRadius: BorderRadius.all(
                                  Radius.circular(10),
                                ),
                              ),
                              child: Padding(
                                padding: EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 6,
                                ),
                                child: Text(
                                  'WebRTC',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),

                if (qrLayerOpen)
                  Positioned.fill(
                    child: QrScanFullscreenBody(
                      controller: _scanner ?? _qrOverlayOnlyController!,
                      onBack: () => unawaited(_closeQrFullscreen()),
                      onConfigDetected: _onQrFullscreenDecoded,
                      onDragXChanged: _onQrScanDragXChanged,
                    ),
                  ),

                // «Назад» только на экране трансляции (не при ожидании подключения).
                if (_streaming && !qrLayerOpen)
                  Positioned(
                    left: 4,
                    top:
                        MediaQuery.paddingOf(context).top +
                        _kStreamOverlayTopExtra,
                    child: _buildStreamBackButton(screenW),
                  ),

                if (bottomChrome != null && !qrLayerOpen) bottomChrome,
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Шеврон «тяните вверх» — лёгкое пульсирование масштаба.
class _PulsingPullHintChevron extends StatefulWidget {
  const _PulsingPullHintChevron();

  @override
  State<_PulsingPullHintChevron> createState() =>
      _PulsingPullHintChevronState();
}

class _PulsingPullHintChevronState extends State<_PulsingPullHintChevron>
    with SingleTickerProviderStateMixin {
  static const _rest = 1.0;
  static const _pulse = 0.93;

  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (context, child) {
        final t = CurvedAnimation(
          parent: _c,
          curve: Curves.easeInOutCubic,
        ).value;
        final scale = _pulse + (_rest - _pulse) * t;
        return Transform.scale(scale: scale, child: child);
      },
      child: const Icon(
        Icons.keyboard_arrow_up_rounded,
        color: Colors.white,
        size: 22,
      ),
    );
  }
}

/// Заголовок «Подключение» с зацикленной сменой точек: . .. ... .. .
/// Точки в [SizedBox] фиксированной ширины, чтобы «Подключение» не смещалось.
class _ConnectingTitle extends StatefulWidget {
  const _ConnectingTitle({this.title = 'Подключение'});

  final String title;

  @override
  State<_ConnectingTitle> createState() => _ConnectingTitleState();
}

class _ConnectingTitleState extends State<_ConnectingTitle>
    with SingleTickerProviderStateMixin {
  static const List<String> _dotPhases = ['.', '..', '...', '..', '.'];
  static const double _titleOffsetX = 12;

  /// Максимальная визуальная ширина троеточия при fontSize 16, w600.
  static const double _dotsSlotWidth = 32;

  static const _titleStyle = TextStyle(
    color: Colors.white,
    fontSize: 16,
    fontWeight: FontWeight.w600,
  );

  late final AnimationController _dots;

  @override
  void initState() {
    super.initState();
    _dots = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void dispose() {
    _dots.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _dots,
      builder: (context, _) {
        final n = _dotPhases.length;
        final i = (_dots.value * n).floor().clamp(0, n - 1);
        return Center(
          child: Transform.translate(
            offset: const Offset(_titleOffsetX, 0),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              textBaseline: TextBaseline.alphabetic,
              crossAxisAlignment: CrossAxisAlignment.baseline,
              children: [
                Text(widget.title, style: _titleStyle),
                SizedBox(
                  width: _dotsSlotWidth,
                  child: Text(
                    _dotPhases[i],
                    style: _titleStyle,
                    textAlign: TextAlign.left,
                    maxLines: 1,
                    overflow: TextOverflow.clip,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Волновая пульсация колец и иконки (та же схема, что на десктопе; коэффициенты чуть сильнее/быстрее).
class _BrandIdleHero extends StatefulWidget {
  const _BrandIdleHero({
    required this.centerShowsQrIcon,
    this.onCenterTap,
    this.pullProgress = 0,
    this.idlePullSheet,
  });

  final bool centerShowsQrIcon;
  final VoidCallback? onCenterTap;

  /// 0 = нижний лист свернут, 1 = максимально раскрыт; влияет на сдвиг тени колец вверх.
  final double pullProgress;

  /// [DraggableScrollableSheet] (обёртка [NotificationListener]) — между кольцами и логотипом.
  final Widget? idlePullSheet;

  @override
  State<_BrandIdleHero> createState() => _BrandIdleHeroState();
}

class _BrandIdleHeroState extends State<_BrandIdleHero>
    with SingleTickerProviderStateMixin {
  /// Один полный период фазы 2π за цикл; скорость как у `phase = t * 1.42` (рад/с).
  late final AnimationController _wave;

  @override
  void initState() {
    super.initState();
    final cycleSec = (math.pi * 2.0) / 1.42;
    final micros = (cycleSec * 1000000).round().clamp(1, 100000000);
    _wave = AnimationController(
      vsync: this,
      duration: Duration(microseconds: micros),
    )..repeat();
  }

  @override
  void dispose() {
    _wave.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _wave,
      builder: (context, _) {
        return _buildBrandIdleWaveFrame(
          phase: _wave.value * math.pi * 2.0,
          centerShowsQrIcon: widget.centerShowsQrIcon,
          onCenterTap: widget.onCenterTap,
          pullProgress: widget.pullProgress,
          pullSheet: widget.idlePullSheet,
        );
      },
    );
  }
}
