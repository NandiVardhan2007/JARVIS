import 'package:flutter_test/flutter_test.dart';
import 'package:vision_face/main.dart';

void main() {
  testWidgets('VisionApp instantiation test', (WidgetTester tester) async {
    await tester.runAsync(() async {
      await tester.pumpWidget(const VisionApp());
      expect(find.byType(VisionApp), findsOneWidget);
    });
  });
}




