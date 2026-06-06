import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'protocol.dart';
import 'socket_buffer.dart';

Future<Socket> _openTcp(String host, int port) async {
  final trimmed = host.trim();
  final literal = InternetAddress.tryParse(trimmed);
  if (literal != null) {
    return Socket.connect(
      literal,
      port,
      timeout: const Duration(seconds: 15),
    );
  }
  final v4 = await InternetAddress.lookup(
    trimmed,
    type: InternetAddressType.IPv4,
  );
  if (v4.isEmpty) {
    throw SocketException('No IPv4 address for host: $trimmed', port: port);
  }
  return Socket.connect(
    v4.first,
    port,
    timeout: const Duration(seconds: 15),
  );
}

/// TCP client: HELLO, ingress (SERVER_SESSION, ERROR), исходящие FRAME / CLIENT_SESSION.
class StreamClient {
  Socket? _socket;
  SocketBuffer? _buf;
  bool _helloOk = false;
  bool _disconnectNotified = false;

  /// Сокет закрыт с удалённой стороны.
  void Function()? onDisconnected;

  /// Сообщение SERVER_SESSION с ПК (десктоп всегда в режиме приёма; поле для совместимости).
  void Function(bool live)? onServerSession;

  bool get isConnected => _helloOk && _socket != null;

  Future<HelloOkResult> connect(
    String host,
    int port,
    String token, {
    int clientStreamQuality = 2,
    int frameRotateK = 0,
  }) async {
    try {
      return await _handshake(
        host,
        port,
        token,
        extendedHello: true,
        clientStreamQuality: clientStreamQuality,
        frameRotateK: frameRotateK,
      );
    } on ProtocolException catch (e) {
      if (e.code != errAuthFailed) {
        rethrow;
      }
      await disconnect();
      return _handshake(
        host,
        port,
        token,
        extendedHello: false,
        clientStreamQuality: clientStreamQuality,
        frameRotateK: frameRotateK,
      );
    }
  }

  Future<HelloOkResult> _handshake(
    String host,
    int port,
    String token, {
    required bool extendedHello,
    required int clientStreamQuality,
    required int frameRotateK,
  }) async {
    await disconnect();
    _disconnectNotified = false;
    final socket = await _openTcp(host, port);
    try {
      socket.setOption(SocketOption.tcpNoDelay, true);
    } on Object {
      // Best-effort; not all platforms expose the option the same way.
    }
    _socket = socket;
    _buf = SocketBuffer(socket);
    _helloOk = false;

    socket.add(
      extendedHello
          ? packHello(
              token,
              clientStreamQuality: clientStreamQuality,
              frameRotateK: frameRotateK,
            )
          : packHelloLegacy(token),
    );

    final header = await _buf!.readExact(10);
    final (msgType, length) = parseHeader(header);
    final body = await _buf!.readExact(length);

    if (msgType == typeError) {
      final (msg, code) = parseErrorBody(body);
      await disconnect();
      throw ProtocolException(code, msg);
    }
    if (msgType != typeHelloOk) {
      await disconnect();
      throw ProtocolException(errBadMessage, 'expected HELLO_OK');
    }
    final hello = parseHelloOkBody(body);
    _helloOk = true;

    final sock = socket;
    sock.done.then((_) {
      if (!identical(_socket, sock)) {
        return;
      }
      unawaited(_onRemoteSocketClosed(sock));
    });

    unawaited(_ingressLoop());
    return hello;
  }

  Future<void> _ingressLoop() async {
    try {
      while (_helloOk && _buf != null) {
        final header = await _buf!.readExact(10);
        final (msgType, length) = parseHeader(header);
        final body = await _buf!.readExact(length);
        if (msgType == typeError) {
          parseErrorBody(body);
          await disconnect();
          _notifyDisconnectOnce();
          break;
        }
        if (msgType == typeServerSession) {
          final live = body.isNotEmpty && body[0] != 0;
          onServerSession?.call(live);
          continue;
        }
        // неизвестные типы от сервера игнорируем
      }
    } on Object {
      if (_helloOk) {
        await disconnect();
        _notifyDisconnectOnce();
      }
    }
  }

  void _notifyDisconnectOnce() {
    if (_disconnectNotified) {
      return;
    }
    _disconnectNotified = true;
    onDisconnected?.call();
  }

  Future<void> _onRemoteSocketClosed(Socket sock) async {
    if (!identical(_socket, sock)) {
      return;
    }
    await disconnect();
    _notifyDisconnectOnce();
  }

  Future<void> sendClientSession(bool live) async {
    if (!_helloOk || _socket == null) {
      return;
    }
    try {
      _socket!.add(packClientSession(live));
    } on Object {
      _helloOk = false;
      rethrow;
    }
  }

  void sendFrame(int width, int height, Uint8List jpeg) {
    if (!_helloOk || _socket == null) {
      return;
    }
    try {
      _socket!.add(packFrame(width, height, jpeg));
    } on Object {
      _helloOk = false;
      rethrow;
    }
  }

  Future<void> disconnect() async {
    _helloOk = false;
    final b = _buf;
    _buf = null;
    final s = _socket;
    _socket = null;
    if (b != null) {
      await b.dispose();
    } else if (s != null) {
      await s.close();
    }
  }
}
