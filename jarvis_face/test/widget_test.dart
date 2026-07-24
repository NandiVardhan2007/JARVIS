import 'package:flutter_test/flutter_test.dart';
import 'package:jarvis_face/main.dart';

void main() {
  testWidgets('JarvisApp instantiation test', (WidgetTester tester) async {
    await tester.runAsync(() async {
      await tester.pumpWidget(const JarvisApp());
      expect(find.byType(JarvisApp), findsOneWidget);
    });
  });
}




