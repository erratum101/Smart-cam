import 'dart:async';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// Формат входных пиксельных данных от `camera` пакета.
enum FrameFormat { yuv420Planar, nv21, bgra }

/// Запрос на JPEG-энкодинг одного кадра в отдельном изоляте.
///
/// Конструируем этот объект на main-изоляте из `CameraImage` и отдаём
/// [JpegEncoder.encode]. Изолят сделает YUV→RGB + JPEG не блокируя UI.
class JpegEncodeRequest {
  JpegEncodeRequest({
    required this.width,
    required this.height,
    required this.format,
    required this.yBytes,
    required this.yRow,
    this.uBytes,
    this.vBytes,
    this.uvBytes,
    this.uRow = 0,
    this.vRow = 0,
    this.uvRow = 0,
    this.uPixel = 1,
    this.vPixel = 1,
    this.bgraRow = 0,
    required this.quality,
    required this.mirrorHorizontal,
  });

  final int width;
  final int height;
  final FrameFormat format;

  /// Y-плоскость для YUV или вся BGRA-плоскость, в зависимости от format.
  final Uint8List yBytes;
  final int yRow;

  final Uint8List? uBytes;
  final Uint8List? vBytes;
  final int uRow;
  final int vRow;
  final int uPixel;
  final int vPixel;

  final Uint8List? uvBytes;
  final int uvRow;

  final int bgraRow;

  final int quality;
  final bool mirrorHorizontal;
}

/// Долгоживущий воркер-изолят, который кодирует JPEG.
///
/// Главная мотивация — снять YUV→RGB→JPEG с UI-изолята: на 720p в чистом
/// Dart этот цикл занимает 80-200 мс, и пока он крутится в main, дёргаются
/// анимации, и кадры из `CameraImage`-стрима копятся.
class JpegEncoder {
  Isolate? _isolate;
  SendPort? _send;
  ReceivePort? _recv;
  int _nextId = 0;
  final Map<int, Completer<Uint8List?>> _pending = {};
  Future<void>? _starting;

  Future<void> _ensureStarted() async {
    if (_send != null) return;
    _starting ??= _bootstrap();
    await _starting;
  }

  Future<void> _bootstrap() async {
    final recv = ReceivePort('jpeg-encoder-host');
    _recv = recv;
    final ready = Completer<SendPort>();
    recv.listen((msg) {
      if (msg is SendPort) {
        if (!ready.isCompleted) ready.complete(msg);
        return;
      }
      if (msg is Map) {
        final id = msg['id'];
        if (id is int) {
          final c = _pending.remove(id);
          if (c != null && !c.isCompleted) {
            final bytes = msg['bytes'];
            c.complete(bytes is Uint8List ? bytes : null);
          }
        }
      }
    });
    _isolate = await Isolate.spawn<SendPort>(
      _workerMain,
      recv.sendPort,
      debugName: 'jpeg-encoder',
    );
    _send = await ready.future;
  }

  /// Кодирует кадр. Возвращает `null` если encoding не удался (неподдерживаемый
  /// формат и т.п.).
  Future<Uint8List?> encode(JpegEncodeRequest req) async {
    await _ensureStarted();
    final send = _send;
    if (send == null) return null;
    final id = _nextId++;
    final c = Completer<Uint8List?>();
    _pending[id] = c;
    send.send(_requestToMap(id, req));
    return c.future;
  }

  Future<void> dispose() async {
    final iso = _isolate;
    final recv = _recv;
    _isolate = null;
    _send = null;
    _recv = null;
    for (final c in _pending.values) {
      if (!c.isCompleted) c.complete(null);
    }
    _pending.clear();
    iso?.kill(priority: Isolate.immediate);
    recv?.close();
    _starting = null;
  }
}

Map<String, Object?> _requestToMap(int id, JpegEncodeRequest r) => {
  'id': id,
  'w': r.width,
  'h': r.height,
  'fmt': r.format.index,
  'y': r.yBytes,
  'yRow': r.yRow,
  'u': r.uBytes,
  'v': r.vBytes,
  'uv': r.uvBytes,
  'uRow': r.uRow,
  'vRow': r.vRow,
  'uvRow': r.uvRow,
  'uPx': r.uPixel,
  'vPx': r.vPixel,
  'bgraRow': r.bgraRow,
  'q': r.quality,
  'mirror': r.mirrorHorizontal,
};

void _workerMain(SendPort parent) {
  final port = ReceivePort('jpeg-encoder-worker');
  parent.send(port.sendPort);
  port.listen((msg) {
    if (msg is! Map) return;
    final id = msg['id'] as int? ?? -1;
    Uint8List? bytes;
    try {
      bytes = _encodeInWorker(msg);
    } on Object {
      bytes = null;
    }
    parent.send({'id': id, 'bytes': bytes});
  });
}

Uint8List? _encodeInWorker(Map msg) {
  final w = msg['w'] as int;
  final h = msg['h'] as int;
  final fmt = FrameFormat.values[msg['fmt'] as int];
  final quality = msg['q'] as int;
  final mirror = msg['mirror'] as bool;
  final img.Image rgb;
  switch (fmt) {
    case FrameFormat.yuv420Planar:
      rgb = _yuvPlanarToRgb(
        w,
        h,
        msg['y'] as Uint8List,
        msg['u'] as Uint8List,
        msg['v'] as Uint8List,
        msg['yRow'] as int,
        msg['uRow'] as int,
        msg['vRow'] as int,
        msg['uPx'] as int,
        msg['vPx'] as int,
      );
      break;
    case FrameFormat.nv21:
      rgb = _nv21ToRgb(
        w,
        h,
        msg['y'] as Uint8List,
        msg['uv'] as Uint8List,
        msg['yRow'] as int,
        msg['uvRow'] as int,
      );
      break;
    case FrameFormat.bgra:
      rgb = _bgraToRgb(
        w,
        h,
        msg['y'] as Uint8List,
        msg['bgraRow'] as int,
      );
      break;
  }
  if (mirror) {
    img.flip(rgb, direction: img.FlipDirection.horizontal);
  }
  return Uint8List.fromList(img.encodeJpg(rgb, quality: quality));
}

img.Image _yuvPlanarToRgb(
  int w,
  int h,
  Uint8List yBytes,
  Uint8List uBytes,
  Uint8List vBytes,
  int yRow,
  int uRow,
  int vRow,
  int uPixel,
  int vPixel,
) {
  final out = img.Image(width: w, height: h);
  for (var y = 0; y < h; y++) {
    final yRowOff = y * yRow;
    final uvRow0 = (y >> 1);
    final uRowOff = uvRow0 * uRow;
    final vRowOff = uvRow0 * vRow;
    for (var x = 0; x < w; x++) {
      final yp = yBytes[yRowOff + x];
      final uvCol = x >> 1;
      final up = uBytes[uRowOff + uvCol * uPixel];
      final vp = vBytes[vRowOff + uvCol * vPixel];
      _setYuv(out, x, y, yp, up, vp);
    }
  }
  return out;
}

img.Image _nv21ToRgb(
  int w,
  int h,
  Uint8List yBytes,
  Uint8List uvBytes,
  int yRow,
  int uvRow,
) {
  final out = img.Image(width: w, height: h);
  for (var y = 0; y < h; y++) {
    final yRowOff = y * yRow;
    final uvRowOff = (y >> 1) * uvRow;
    for (var x = 0; x < w; x++) {
      final yp = yBytes[yRowOff + x];
      final uvIndex = uvRowOff + (x >> 1) * 2;
      final v = uvBytes[uvIndex];
      final u = uvBytes[uvIndex + 1];
      _setYuv(out, x, y, yp, u, v);
    }
  }
  return out;
}

img.Image _bgraToRgb(int w, int h, Uint8List bytes, int rowStride) {
  final out = img.Image(width: w, height: h);
  for (var y = 0; y < h; y++) {
    final rowOff = y * rowStride;
    for (var x = 0; x < w; x++) {
      final o = rowOff + x * 4;
      final b = bytes[o];
      final g = bytes[o + 1];
      final r = bytes[o + 2];
      out.setPixelRgb(x, y, r, g, b);
    }
  }
  return out;
}

void _setYuv(img.Image out, int x, int y, int yp, int u, int v) {
  final r = (yp + 1.402 * (v - 128)).round().clamp(0, 255);
  final g = (yp - 0.344136 * (u - 128) - 0.714136 * (v - 128))
      .round()
      .clamp(0, 255);
  final b = (yp + 1.772 * (u - 128)).round().clamp(0, 255);
  out.setPixelRgb(x, y, r, g, b);
}
