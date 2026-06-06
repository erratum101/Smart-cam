import 'dart:convert';

/// Payload v1 from PC QR: `{"v":1,"h":"ip","p":17777,"t":"token"}`.
class QrConnectConfig {
  const QrConnectConfig({
    required this.host,
    required this.port,
    required this.token,
    this.mode,
    this.signalingPort,
    this.name,
    this.lanHost,
  });

  final String host;
  final int port;
  final String token;
  final String? mode;
  final int? signalingPort;
  /// LAN IP ПК для WebRTC, когда [host] — loopback (USB/adb).
  final String? lanHost;
  /// Display name of the PC (hostname), e.g. "DESKTOP-ABCD12".
  final String? name;

  /// Label shown in chips: PC name if available, otherwise host IP.
  String get displayName => (name != null && name!.isNotEmpty) ? name! : host;

  /// Returns null if string is not a valid Smart Cam QR payload.
  static QrConnectConfig? tryParse(String raw) {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) return null;
    try {
      final decoded = jsonDecode(trimmed);
      if (decoded is! Map<String, dynamic>) return null;
      final v = decoded['v'];
      if (v != 1 && v != 2) return null;
      final h = decoded['h'];
      final t = decoded['t'];
      final p = decoded['p'];
      final m = decoded['m'];
      final sp = decoded['sp'];
      final n = decoded['n'];
      if (h is! String || t is! String) return null;
      final port = p is int ? p : int.tryParse('$p');
      if (port == null || port <= 0 || port > 65535) return null;
      final signalingPort = sp == null
          ? null
          : (sp is int ? sp : int.tryParse('$sp'));
      if (signalingPort != null &&
          (signalingPort <= 0 || signalingPort > 65535)) {
        return null;
      }
      if (h.isEmpty || t.isEmpty) return null;
      return QrConnectConfig(
        host: h,
        port: port,
        token: t,
        mode: m is String && m.trim().isNotEmpty
            ? m.trim().toLowerCase()
            : null,
        signalingPort: signalingPort,
        name: n is String && n.trim().isNotEmpty ? n.trim() : null,
      );
    } on Object {
      return null;
    }
  }
}
