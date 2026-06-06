// ignore_for_file: avoid_print

import 'dart:io';

import 'package:image/image.dart';

/// Иконка Android 12+ обрезается по кругу — добавляем прозрачные поля вокруг [../icon.png].
void main() {
  final mobileRoot = Directory.current;
  final repoRoot = mobileRoot.parent;
  final srcFile = File('${repoRoot.path}${Platform.pathSeparator}icon.png');
  if (!srcFile.existsSync()) {
    print('Не найден ${srcFile.path}');
    exit(1);
  }
  final src = decodeImage(srcFile.readAsBytesSync());
  if (src == null) {
    print('Не удалось прочитать PNG');
    exit(1);
  }
  // ~30% поля с каждой стороны: логотип помещается в «безопасную» зону круга.
  const padFactor = 1.65;
  final outW = (src.width * padFactor).round();
  final outH = (src.height * padFactor).round();
  final out = Image(width: outW, height: outH, numChannels: 4);
  fill(out, color: ColorRgba8(0, 0, 0, 0));
  compositeImage(
    out,
    src,
    dstX: (outW - src.width) ~/ 2,
    dstY: (outH - src.height) ~/ 2,
  );
  final outDir = Directory('${mobileRoot.path}/assets');
  outDir.createSync(recursive: true);
  final outPath = File('${outDir.path}/splash_android12.png');
  outPath.writeAsBytesSync(encodePng(out));
  print('OK -> ${outPath.path} (${outW}x$outH)');
}
