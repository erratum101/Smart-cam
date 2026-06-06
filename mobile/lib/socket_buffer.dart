import 'dart:async';
import 'dart:collection';
import 'dart:io';
import 'dart:typed_data';

/// Buffered reads from a [Socket] for length-prefixed protocol parsing.
class SocketBuffer {
  SocketBuffer(this._socket) {
    _subscription = _socket.listen(
      _onData,
      onError: (Object e, _) => _error = e,
      onDone: () {
        _closed = true;
        _completeWaiters();
      },
      cancelOnError: false,
    );
  }

  final Socket _socket;
  late final StreamSubscription<List<int>> _subscription;
  final Queue<Uint8List> _parts = Queue();
  int _firstOffset = 0;
  Object? _error;
  bool _closed = false;
  final List<Completer<void>> _waiters = [];

  Socket get socket => _socket;

  int get _bufferedLength {
    if (_parts.isEmpty) return 0;
    var total = 0;
    for (final p in _parts) {
      total += p.length;
    }
    return total - _firstOffset;
  }

  void _onData(List<int> data) {
    _parts.add(data is Uint8List ? data : Uint8List.fromList(data));
    _completeWaiters();
  }

  void _completeWaiters() {
    for (final w in _waiters) {
      if (!w.isCompleted) w.complete();
    }
    _waiters.clear();
  }

  Future<void> _waitForData() async {
    if (_bufferedLength > 0) return;
    if (_error != null) {
      throw _error!;
    }
    if (_closed) {
      throw StateError('Socket closed');
    }
    final c = Completer<void>();
    _waiters.add(c);
    await c.future;
    if (_error != null) {
      throw _error!;
    }
    if (_bufferedLength == 0 && _closed) {
      throw StateError('EOF');
    }
  }

  int _readInto(Uint8List dst, int dstOffset, int max) {
    var written = 0;
    while (written < max && _parts.isNotEmpty) {
      final head = _parts.first;
      final start = _firstOffset;
      final avail = head.length - start;
      final take = avail < (max - written) ? avail : (max - written);
      dst.setRange(
        dstOffset + written,
        dstOffset + written + take,
        head,
        start,
      );
      written += take;
      _firstOffset += take;
      if (_firstOffset >= head.length) {
        _parts.removeFirst();
        _firstOffset = 0;
      }
    }
    return written;
  }

  Future<Uint8List> readExact(int n) async {
    final out = Uint8List(n);
    var got = 0;
    while (got < n) {
      if (_bufferedLength == 0) {
        await _waitForData();
      }
      if (_bufferedLength == 0) {
        if (_closed) {
          throw StateError('EOF');
        }
        continue;
      }
      got += _readInto(out, got, n - got);
    }
    return out;
  }

  Future<void> dispose() async {
    await _subscription.cancel();
    await _socket.close();
  }
}
