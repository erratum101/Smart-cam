import 'package:flutter_test/flutter_test.dart';

import 'package:smart_cam_mobile/main.dart';

void main() {
  testWidgets('App builds', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartCamApp());
    expect(find.text('Предпросмотр'), findsOneWidget);
  });
}
