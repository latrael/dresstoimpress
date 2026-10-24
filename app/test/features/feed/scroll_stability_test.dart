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

Future<void> mount(WidgetTester tester, {bool long = false}) async {
  tester.view.physicalSize = const Size(420, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(
      home: Scaffold(
          body: QuickBrowse(
    products: [piece('a', long: long), piece('b'), piece('c')],
    savedIds: const {},
    onSave: (_, value) async {},
    onAddToCart: (_, size) async {},
    imageUrl: (s) => s,
  ))));
  await tester.pumpAndSettle();
}

Finder details(String id) => find.byKey(ValueKey('details-$id'));
PageController productPages(WidgetTester tester) =>
    tester.widget<PageView>(find.byType(PageView).first).controller!;
Future<void> wheel(WidgetTester tester, double dy) async {
  await tester.sendEventToBinding(PointerScrollEvent(
      position: const Offset(200, 600), scrollDelta: Offset(0, dy)));
  await tester.pump();
}

void main() {
  testWidgets('tiny reverse drag at top does not twitch to previous product',
      (tester) async {
    await mount(tester);
    await tester.drag(details('a'), const Offset(0, -1000));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
    await tester.drag(details('b'), const Offset(0, 30));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
  });
  testWidgets('small wheel overflow stays on current product', (tester) async {
    await mount(tester);
    await wheel(tester, 20);
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 0);
  });
  testWidgets('one continuous wheel burst advances only one product',
      (tester) async {
    await mount(tester);
    for (var i = 0; i < 12; i++) {
      await wheel(tester, 40);
      await tester.pump(const Duration(milliseconds: 45));
    }
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
    await tester.pump(const Duration(milliseconds: 300));
    for (var i = 0; i < 4; i++) {
      await wheel(tester, 40);
      await tester.pump(const Duration(milliseconds: 30));
    }
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 2);
  });
  testWidgets('description scroll and its fling do not skip the next product',
      (tester) async {
    await mount(tester, long: true);
    await tester.fling(details('a'), const Offset(0, -200), 2200);
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 0);
  });
  testWidgets('a deliberate touch drag changes product only after release',
      (tester) async {
    await mount(tester);
    final gesture = await tester.startGesture(const Offset(200, 650));
    await gesture.moveBy(const Offset(0, -160));
    await tester.pump(const Duration(milliseconds: 400));
    expect(productPages(tester).page, 0);
    expect(find.text('Release for next item'), findsOneWidget);
    await gesture.up();
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
  });
  testWidgets(
      'wheel gesture that scrolls details cannot carry into another product',
      (tester) async {
    await mount(tester, long: true);
    for (var i = 0; i < 30; i++) {
      await wheel(tester, 50);
      await tester.pump(const Duration(milliseconds: 25));
    }
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 0);
    // A separate gesture begun at the bottom deliberately advances.
    await tester.pump(const Duration(milliseconds: 300));
    for (var i = 0; i < 4; i++) {
      await wheel(tester, 40);
    }
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
  });
  testWidgets(
      'up-arrow cue appears only past the boundary and confirms before moving',
      (tester) async {
    await mount(tester);
    expect(find.text('Keep scrolling for next item'), findsNothing);
    await wheel(tester, 20);
    expect(find.text('Keep scrolling for next item'), findsOneWidget);
    expect(find.byIcon(Icons.keyboard_arrow_up), findsOneWidget);
    expect(productPages(tester).page, 0);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Keep scrolling for next item'), findsNothing);
    await wheel(tester, 130);
    expect(find.text('Next item ready'), findsOneWidget);
    expect(productPages(tester).page, 0);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(productPages(tester).page, 1);
  });
}
