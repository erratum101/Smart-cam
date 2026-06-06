import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:multicast_dns/multicast_dns.dart';

import 'qr_config.dart';

/// Порт HTTP-обнаружения на ПК (только через ADB reverse, 127.0.0.1).
const _kDiscoveryPort = 17776;

/// mDNS тип сервиса (совпадает с регистрацией на ПК).
const _kMdnsServiceType = '_smartcam._tcp';

bool _isLoopbackHost(String host) {
  final h = host.trim().toLowerCase();
  return h == '127.0.0.1' || h == 'localhost' || h == '::1';
}

/// Ищет ПК по mDNS (WiFi) и через HTTP-запрос к 127.0.0.1 (USB/ADB).
///
/// Если доступны оба, предпочитает LAN (mDNS): WebRTC по UDP не работает
/// через `127.0.0.0.1` без проброса медиа-портов, а TCP по USB остаётся
/// запасным путём при loopback-хосте.
Future<QrConnectConfig?> discoverHost({
  Duration timeout = const Duration(seconds: 5),
}) async {
  QrConnectConfig? usb;
  QrConnectConfig? mdns;

  try {
    await Future.wait([
      _tryUsbDiscovery().then((v) => usb = v).catchError((_) => null),
      _tryMdnsDiscovery().then((v) => mdns = v).catchError((_) => null),
    ]).timeout(timeout);
  } on TimeoutException {
    // use partial results
  } on Object {
    // Без Wi‑Fi mDNS может бросить SocketException (errno 101) — не роняем цикл.
  }

  if (mdns != null && !_isLoopbackHost(mdns!.host)) {
    return mdns;
  }
  return usb ?? mdns;
}

/// Пробует получить конфиг через HTTP GET 127.0.0.1:{_kDiscoveryPort}/info.
Future<QrConnectConfig?> _tryUsbDiscovery() async {
  try {
    final uri = Uri.parse('http://127.0.0.1:$_kDiscoveryPort/info');
    final response = await http.get(uri).timeout(const Duration(seconds: 3));
    if (response.statusCode == 200) {
      return _parseInfoJson(response.body, '127.0.0.1');
    }
  } on Object {
    // ПК недоступен по USB — тихо игнорируем.
  }
  return null;
}

/// Фабрика сокетов для MDnsClient с fallback: если reusePort не поддерживается
/// платформой (некоторые MIUI/Android-устройства), пробуем без него.
Future<RawDatagramSocket> _mdnsSocketFactory(
  dynamic host,
  int port, {
  bool reuseAddress = false,
  bool reusePort = false,
  int ttl = 1,
}) async {
  try {
    return await RawDatagramSocket.bind(
      host,
      port,
      reuseAddress: reuseAddress,
      reusePort: reusePort,
      ttl: ttl,
    );
  } on SocketException {
    return await RawDatagramSocket.bind(
      host,
      port,
      reuseAddress: reuseAddress,
      reusePort: false,
      ttl: ttl,
    );
  }
}

/// Сканирует mDNS для типа [_kMdnsServiceType].
Future<QrConnectConfig?> _tryMdnsDiscovery() async {
  MDnsClient? client;
  try {
    client = MDnsClient(rawDatagramSocketFactory: _mdnsSocketFactory);
    await client.start();

    await for (final PtrResourceRecord ptr in client
        .lookup<PtrResourceRecord>(
          ResourceRecordQuery.serverPointer(_kMdnsServiceType),
        )
        .timeout(const Duration(seconds: 4), onTimeout: (_) {})) {
      await for (final SrvResourceRecord srv in client
          .lookup<SrvResourceRecord>(
            ResourceRecordQuery.service(ptr.domainName),
          )
          .timeout(const Duration(seconds: 2), onTimeout: (_) {})) {
        final int port = srv.port;
        String? token;
        String? mdnsName;
        int? mdnsSignalingPort;
        String? mdnsMode;
        await for (final TxtResourceRecord txt in client
            .lookup<TxtResourceRecord>(
              ResourceRecordQuery.text(ptr.domainName),
            )
            .timeout(const Duration(seconds: 2), onTimeout: (_) {})) {
          for (final entry in txt.text.split('\n')) {
            final kv = entry.split('=');
            if (kv.length == 2) {
              final key = kv[0].trim();
              final val = kv[1].trim();
              if (key == 't') token = val;
              if (key == 'n' && val.isNotEmpty) mdnsName = val;
              if (key == 'sp' && val.isNotEmpty) {
                mdnsSignalingPort = int.tryParse(val);
              }
              if (key == 'm' && val.isNotEmpty) {
                mdnsMode = val.toLowerCase();
              }
            }
          }
          if (token != null) break;
        }

        if (token == null) continue;

        await for (final IPAddressResourceRecord ip in client
            .lookup<IPAddressResourceRecord>(
              ResourceRecordQuery.addressIPv4(srv.target),
            )
            .timeout(const Duration(seconds: 2), onTimeout: (_) {})) {
          final host = ip.address.address;
          return QrConnectConfig(
            host: host,
            port: port,
            token: token,
            name: mdnsName,
            signalingPort: (mdnsSignalingPort != null &&
                    mdnsSignalingPort > 0 &&
                    mdnsSignalingPort <= 65535)
                ? mdnsSignalingPort
                : null,
            mode: mdnsMode,
          );
        }
      }
    }
  } on Object {
    // mDNS недоступен — тихо игнорируем.
  } finally {
    try {
      client?.stop();
    } on Object {
      // ignore
    }
  }
  return null;
}

QrConnectConfig? _parseInfoJson(String body, String fallbackHost) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) return null;
    final p = decoded['p'];
    final t = decoded['t'];
    final n = decoded['n'];
    final sp = decoded['sp'];
    final m = decoded['m'];
    if (t is! String || t.isEmpty) return null;
    final port = p is int ? p : int.tryParse('$p');
    if (port == null || port <= 0 || port > 65535) return null;
    final signalingPort = sp == null
        ? null
        : (sp is int ? sp : int.tryParse('$sp'));
    final lip = decoded['lip'];
    final lanHost = lip is String && lip.isNotEmpty && !_isLoopbackHost(lip)
        ? lip.trim()
        : null;
    return QrConnectConfig(
      host: fallbackHost,
      port: port,
      token: t,
      name: n is String && n.isNotEmpty ? n : null,
      signalingPort:
          signalingPort != null && signalingPort > 0 && signalingPort <= 65535
              ? signalingPort
              : null,
      mode: m is String && m.trim().isNotEmpty ? m.trim().toLowerCase() : null,
      lanHost: lanHost,
    );
  } on Object {
    return null;
  }
}
