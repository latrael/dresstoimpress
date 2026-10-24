import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dress_to_impress/features/feed/quick_browse.dart';

Map<String, dynamic> piece(String id, {bool long = false}) => {
      'id': id,
      'name': 'Piece $id',
      'price_usd': 20,
      'images': [],
      'description': long
          ? List.filled(50, 'A long retailer description.').join(' ')
          : 'Description $id',
      'in_stock': true,
      'sizes': [
        {'name': 'S', 'in_stock': true}
      ],
    };

Future<void> mount(WidgetTester tester,
    {bool long = false, int count = 3}) async {
  tester.view.physicalSize = const Size(420, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(
      home: Scaffold(
          body: QuickBrowse(
    products: List.generate(count, (i) => piece('$i', long: long && i == 0)),
    savedIds: const {},
    onSave: (_, value) async {},
    onAddToCart: (_, size) async {},
    imageUrl: (s) => s,
  ))));
  await tester.pumpAndSettle();
}

Finder stream() => find.byKey(const ValueKey('product-stream'));
ScrollPosition position(WidgetTester tester) => tester
    .state<ScrollableState>(
        find.descendant(of: stream(), matching: find.byType(Scrollable)).first)
    .position;

void main() {
  testWidgets('a single upward drag crosses straight into the next product',
      (tester) async {
    await mount(tester);
    final start = tester.getTopLeft(find.text('Piece 1')).dy;
    final gesture = await tester.startGesture(const Offset(200, 650));
    await gesture.moveBy(const Offset(0, -650));
    await tester.pump();
    expect(position(tester).pixels, greaterThan(500));
    expect(tester.getTopLeft(find.text('Piece 1')).dy, lessThan(start - 500));
    expect(find.byIcon(Icons.keyboard_arrow_up), findsNothing);
    await gesture.up();
    await tester.pumpAndSettle();
  });
  testWidgets('long descriptions and the next item share one vertical scroll',
      (tester) async {
    await mount(tester, long: true);
    expect(find.byType(SingleChildScrollView), findsNothing);
    await tester.drag(stream(), const Offset(0, -300));
    await tester.pumpAndSettle();
    final before = position(tester).pixels;
    expect(before, greaterThan(0));
    await tester.scrollUntilVisible(find.text('Piece 1'), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    expect(position(tester).pixels, greaterThan(before));
    expect(find.text('Piece 1').hitTestable(), findsOneWidget);
  });
  testWidgets('wheel scroll advances continuously without an idle confirmation',
      (tester) async {
    await mount(tester);
    for (var i = 0; i < 8; i++) {
      await tester.sendEventToBinding(const PointerScrollEvent(
          position: Offset(200, 650), scrollDelta: Offset(0, 100)));
      await tester.pump();
      expect(position(tester).pixels, closeTo((i + 1) * 100, 1));
    }
    expect(find.text('Piece 1').hitTestable(), findsOneWidget);
  });
  testWidgets(
      'only nearby products are built, distant products appear on approach',
      (tester) async {
    await mount(tester, count: 60);
    expect(find.text('Piece 0'), findsOneWidget);
    expect(find.text('Piece 59'), findsNothing);
    expect(find.byKey(const ValueKey('details-30')), findsNothing);
    await tester.scrollUntilVisible(find.text('Piece 6'), 500,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    expect(find.text('Piece 6').hitTestable(), findsOneWidget);
    expect(find.text('Piece 59'), findsNothing);
    expect(find.text('Piece 0'), findsNothing);
  });
  testWidgets('a thick solid separator lies between consecutive products',
      (tester) async {
    await mount(tester);
    final marker = find.byKey(const ValueKey('product-separator-0'));
    expect(tester.getSize(marker).height, 72);
    expect(tester.widget<Container>(marker).color, const Color(0xFFBDA7AD));
    expect(tester.getBottomLeft(find.byKey(const ValueKey('details-0'))).dy,
        lessThanOrEqualTo(tester.getTopLeft(marker).dy));
    expect(
        tester.getBottomLeft(marker).dy,
        lessThanOrEqualTo(
            tester.getTopLeft(find.byKey(const ValueKey('details-1'))).dy));
  });
}
