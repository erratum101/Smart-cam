import 'package:flutter/material.dart';

/// Brand palette for Smart Cam.
abstract final class AppColors {
  static const Color accent = Color(0xFF002EE8);
  static const Color white = Color(0xFFFFFFFF);
  static const Color dark = Color(0xFF222222);
  static const Color danger = Color(0xFFE80000);

  /// Inputs / elevated surfaces on dark UI.
  static const Color darkElevated = Color(0xFF333333);

  /// Secondary pill (Preview / Scan) on transparent bar over camera.
  static const Color previewPillBg = Color(0xFFE6E6E6);
}
