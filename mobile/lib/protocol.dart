import 'dart:convert';
import 'dart:typed_data';

/// Protocol v1 — see docs/PROTOCOL.md
const magic = [0x53, 0x43, 0x57, 0x42]; // SCWB
const protocolVersion = 1;

const typeHello = 1;
const typeHelloOk = 2;
const typeFrame = 3;
const typeServerSession = 4;
const typeClientSession = 5;
const typeError = 255;

/// Результат HELLO_OK: качество потока (эхо HELLO) и жив ли сеанс на ПК.
typedef HelloOkResult = ({int qualityIndex, bool pcSessionLive});

const errAuthFailed = 1;
const errBadMessage = 2;
const errServerError = 3;

Uint8List packMessage(int msgType, List<int> body) {
  final len = body.length;
  final out = Uint8List(10 + len);
  out.setRange(0, 4, magic);
  out[4] = protocolVersion;
  out[5] = msgType;
  out[6] = (len >> 24) & 0xff;
  out[7] = (len >> 16) & 0xff;
  out[8] = (len >> 8) & 0xff;
  out[9] = len & 0xff;
  out.setRange(10, 10 + len, body);
  return out;
}

/// HELLO только токен (старые серверы без расширенного разбора body).
Uint8List packHelloLegacy(String token) {
  return packMessage(typeHello, utf8.encode(token));
}

/// HELLO body: UTF-8 токен, NUL, качество 0=low..2=high, [frame_rotate_k 0..3].
Uint8List packHello(
  String token, {
  int clientStreamQuality = 2,
  int frameRotateK = 0,
}) {
  final tb = utf8.encode(token);
  final q = clientStreamQuality.clamp(0, 2);
  final rk = frameRotateK.clamp(0, 3);
  final body = Uint8List(tb.length + 3);
  body.setRange(0, tb.length, tb);
  body[tb.length] = 0;
  body[tb.length + 1] = q;
  body[tb.length + 2] = rk;
  return packMessage(typeHello, body);
}

HelloOkResult parseHelloOkBody(Uint8List body) {
  var qualityIndex = 1;
  if (body.isNotEmpty) {
    final v = body[0];
    if (v <= 2) {
      qualityIndex = v;
    }
  }
  final pcSessionLive = body.length >= 2 && body[1] != 0;
  return (qualityIndex: qualityIndex, pcSessionLive: pcSessionLive);
}

Uint8List packClientSession(bool live) {
  return packMessage(typeClientSession, [live ? 1 : 0]);
}

Uint8List packFrame(int width, int height, Uint8List jpeg) {
  final body = Uint8List(12 + jpeg.length);
  final bd = ByteData.sublistView(body);
  bd.setUint32(0, width, Endian.big);
  bd.setUint32(4, height, Endian.big);
  bd.setUint32(8, jpeg.length, Endian.big);
  body.setRange(12, 12 + jpeg.length, jpeg);
  return packMessage(typeFrame, body);
}

class ProtocolException implements Exception {
  ProtocolException(this.code, this.message);
  final int code;
  final String message;

  @override
  String toString() => 'ProtocolException($code): $message';
}

/// Parse server header; returns (type, bodyLength).
(int, int) parseHeader(Uint8List header) {
  if (header.length != 10) {
    throw ProtocolException(errBadMessage, 'short header');
  }
  for (var i = 0; i < 4; i++) {
    if (header[i] != magic[i]) {
      throw ProtocolException(errBadMessage, 'bad magic');
    }
  }
  if (header[4] != protocolVersion) {
    throw ProtocolException(errBadMessage, 'bad version');
  }
  final msgType = header[5];
  final length = (header[6] << 24) | (header[7] << 16) | (header[8] << 8) | header[9];
  return (msgType, length);
}

(String message, int code) parseErrorBody(Uint8List body) {
  if (body.length < 4) {
    return ('short error', errBadMessage);
  }
  final bd = ByteData.sublistView(body);
  final code = bd.getUint16(0, Endian.big);
  final mlen = bd.getUint16(2, Endian.big);
  if (body.length < 4 + mlen) {
    return ('truncated error', code);
  }
  final text = utf8.decode(body.sublist(4, 4 + mlen));
  return (text, code);
}
