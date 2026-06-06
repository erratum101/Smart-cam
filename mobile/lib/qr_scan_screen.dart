import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import 'qr_config.dart';

/// Радиус, визуально близкий к скруглению рамки дисплея (логические пиксели).
double qrScanDisplayCornerRadius(BuildContext context) {
  final s = MediaQuery.sizeOf(context);
  return (s.shortestSide * 0.052).clamp(18.0, 44.0);
}

/// Полноэкранный слой сканера (без нижней панели — её рисует родитель).
class QrScanFullscreenBody extends StatefulWidget {
  const QrScanFullscreenBody({
    super.key,
    required this.controller,
    required this.onBack,
    required this.onConfigDetected,
    this.onDragXChanged,
  });

  final MobileScannerController controller;
  final VoidCallback onBack;
  final Future<void> Function(QrConnectConfig config) onConfigDetected;

  /// Текущий сдвиг слоя вправо (0…ширина экрана) — для параллакса подложки.
  final ValueChanged<double>? onDragXChanged;

  @override
  State<QrScanFullscreenBody> createState() => _QrScanFullscreenBodyState();
}

class _QrScanFullscreenBodyState extends State<QrScanFullscreenBody> {
  bool _handled = false;

  /// Показываем маску и углы только после композиции BackdropFilter — без «сначала углы».
  bool _showChrome = false;
  double _dragX = 0;
  bool _dismissing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _showChrome = true);
      });
    });
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_handled) return;
    final barcodes = capture.barcodes;
    if (barcodes.isEmpty) return;
    final raw = barcodes.first.rawValue;
    if (raw == null || raw.isEmpty) return;
    final cfg = QrConnectConfig.tryParse(raw);
    if (cfg == null) return;
    _handled = true;
    await widget.controller.stop();
    if (!mounted) return;
    await widget.onConfigDetected(cfg);
  }

  void _emitDragX(double x) {
    widget.onDragXChanged?.call(x);
  }

  Future<void> _animateDismiss() async {
    if (_dismissing) return;
    _dismissing = true;
    final screenW = MediaQuery.sizeOf(context).width;
    const step = Duration(milliseconds: 14);
    while (mounted && _dragX < screenW * 0.98) {
      setState(() {
        _dragX += (screenW * 1.02 - _dragX) * 0.32;
        if (_dragX > screenW) _dragX = screenW;
      });
      _emitDragX(_dragX);
      await Future<void>.delayed(step);
    }
    if (mounted) {
      widget.onBack();
    }
  }

  @override
  Widget build(BuildContext context) {
    final screenW = MediaQuery.sizeOf(context).width;
    final cornerR = qrScanDisplayCornerRadius(context);

    return Transform.translate(
      offset: Offset(_dragX, 0),
      child: Material(
        color: Colors.transparent,
        elevation: _dragX > 0 ? 10 : 0,
        shadowColor: Colors.black54,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(cornerR)),
        ),
        child: Stack(
          fit: StackFit.expand,
          children: [
            MobileScanner(
              controller: widget.controller,
              onDetect: _onDetect,
              useAppLifecycleState: false,
              fit: BoxFit.cover,
            ),
            LayoutBuilder(
              builder: (context, constraints) {
                final w = constraints.maxWidth;
                final h = constraints.maxHeight;
                final side = (math.min(w, h) * 0.64).clamp(220.0, 360.0);
                final left = (w - side) / 2;
                final top = h * 0.26;
                final hole = RRect.fromRectAndRadius(
                  Rect.fromLTWH(left, top, side, side),
                  const Radius.circular(32),
                );
                return Opacity(
                  opacity: _showChrome ? 1 : 0,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      ClipPath(
                        clipper: _ScannerHoleClipper(hole: hole),
                        child: BackdropFilter(
                          filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
                          child: const ColoredBox(
                            color: Color.fromARGB(206, 0, 46, 232),
                          ),
                        ),
                      ),
                      CustomPaint(
                        painter: _ScannerCornersPainter(hole: hole),
                        size: Size.infinite,
                      ),
                      Positioned(
                        left: 24,
                        right: 24,
                        top: top + side + 28,
                        child: const IgnorePointer(
                          child: Text(
                            'Наведите камеру на QR в приложении\nна вашем компьютере',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              height: 1.3,
                              fontWeight: FontWeight.w500,
                              shadows: [
                                Shadow(
                                  color: Color(0x66000000),
                                  blurRadius: 6,
                                  offset: Offset(0, 1),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
            // Верхний слой: свайп с любой точки — слой съезжает вправо, слева виден экран под ним.
            if (!_dismissing)
              Positioned.fill(
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onHorizontalDragUpdate: (d) {
                    if (_dismissing) return;
                    setState(() {
                      _dragX = (_dragX + d.delta.dx).clamp(0.0, screenW);
                    });
                    _emitDragX(_dragX);
                  },
                  onHorizontalDragEnd: (d) {
                    if (_dismissing) return;
                    final v = d.primaryVelocity ?? 0;
                    if (_dragX > screenW * 0.18 || v > 550) {
                      unawaited(_animateDismiss());
                    } else {
                      setState(() => _dragX = 0);
                      _emitDragX(0);
                    }
                  },
                  onHorizontalDragCancel: () {
                    if (_dismissing) return;
                    if (_dragX > 0) {
                      setState(() => _dragX = 0);
                      _emitDragX(0);
                    }
                  },
                  child: const ColoredBox(color: Colors.transparent),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Вырез «окна» сканера: всё кроме [hole] — под блюр и синюю подложку.
class _ScannerHoleClipper extends CustomClipper<Path> {
  const _ScannerHoleClipper({required this.hole});

  final RRect hole;

  @override
  Path getClip(Size size) {
    return Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addRRect(hole);
  }

  @override
  bool shouldReclip(covariant _ScannerHoleClipper oldClipper) =>
      oldClipper.hole != hole;
}

class _ScannerCornersPainter extends CustomPainter {
  _ScannerCornersPainter({required this.hole});

  final RRect hole;

  static Path _bracketTopLeft(RRect g, double arm) {
    final l = g.left;
    final t = g.top;
    final rad = g.tlRadius.x;
    final c = Offset(l + rad, t + rad);
    return Path()
      ..moveTo(l + rad + arm, t)
      ..lineTo(l + rad, t)
      ..arcTo(
        Rect.fromCircle(center: c, radius: rad),
        -math.pi / 2,
        -math.pi / 2,
        false,
      )
      ..lineTo(l, t + rad + arm);
  }

  static Path _bracketTopRight(RRect g, double arm) {
    final r = g.right;
    final t = g.top;
    final rad = g.trRadius.x;
    final c = Offset(r - rad, t + rad);
    return Path()
      ..moveTo(r - rad - arm, t)
      ..lineTo(r - rad, t)
      ..arcTo(
        Rect.fromCircle(center: c, radius: rad),
        -math.pi / 2,
        math.pi / 2,
        false,
      )
      ..lineTo(r, t + rad + arm);
  }

  static Path _bracketBottomLeft(RRect g, double arm) {
    final l = g.left;
    final b = g.bottom;
    final rad = g.blRadius.x;
    final c = Offset(l + rad, b - rad);
    return Path()
      ..moveTo(l + rad + arm, b)
      ..lineTo(l + rad, b)
      ..arcTo(
        Rect.fromCircle(center: c, radius: rad),
        math.pi / 2,
        math.pi / 2,
        false,
      )
      ..lineTo(l, b - rad - arm);
  }

  static Path _bracketBottomRight(RRect g, double arm) {
    final r = g.right;
    final b = g.bottom;
    final rad = g.brRadius.x;
    final c = Offset(r - rad, b - rad);
    return Path()
      ..moveTo(r - rad - arm, b)
      ..lineTo(r - rad, b)
      ..arcTo(
        Rect.fromCircle(center: c, radius: rad),
        math.pi / 2,
        -math.pi / 2,
        false,
      )
      ..lineTo(r, b - rad - arm);
  }

  @override
  void paint(Canvas canvas, Size size) {
    // Как в Telegram: зазор от выреза, скруглённый «локоть» по дуге, без сплошной рамки.
    const bracketGap = 7.0;
    const arm = 34.0;
    final guide = hole.inflate(bracketGap);

    final bracket = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = Colors.white;

    canvas.drawPath(_bracketTopLeft(guide, arm), bracket);
    canvas.drawPath(_bracketTopRight(guide, arm), bracket);
    canvas.drawPath(_bracketBottomLeft(guide, arm), bracket);
    canvas.drawPath(_bracketBottomRight(guide, arm), bracket);
  }

  @override
  bool shouldRepaint(covariant _ScannerCornersPainter oldDelegate) =>
      oldDelegate.hole != hole;
}
