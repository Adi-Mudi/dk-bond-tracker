import 'package:flutter_test/flutter_test.dart';

import 'package:app/main.dart';

void main() {
  testWidgets('app renders foundation shell', (WidgetTester tester) async {
    await tester.pumpWidget(const DkBondTrackerApp());
    expect(find.text('DK Bond Tracker'), findsOneWidget);
  });
}
