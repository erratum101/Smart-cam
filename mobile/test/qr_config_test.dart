import 'package:flutter_test/flutter_test.dart';
import 'package:smart_cam_mobile/qr_config.dart';

void main() {
  test('tryParse valid v1 JSON', () {
    final c = QrConnectConfig.tryParse(
      '{"v":1,"h":"192.168.0.5","p":17777,"t":"abc-token"}',
    );
    expect(c, isNotNull);
    expect(c!.host, '192.168.0.5');
    expect(c.port, 17777);
    expect(c.token, 'abc-token');
  });

  test('tryParse rejects wrong version', () {
    expect(
      QrConnectConfig.tryParse('{"v":2,"h":"x","p":1,"t":"y"}'),
      isNull,
    );
  });
}
