import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// ignore: avoid_relative_lib_imports
import '../../../lib/features/feed/quick_browse.dart';

Map<String, dynamic> product(String id, {int photos = 2}) => {
      'id': id,
      'name': 'Piece $id',
      'brand': 'H&M',
      'price_usd': 20,
      'description': 'Description for $id',
      'in_stock': true,
      'images': List.generate(
        photos,
        (i) => {'url': 'https://example.com/$id/$i.jpg'},
      ),
      'sizes': [
        {'name': 'S', 'in_stock': true},
        {'name': 'M', 'in_stock': false},
      ],
    };

void main() {
  Future<void> mount(
    WidgetTester tester, {
    Future<void> Function(String, String)? cart,
    Future<void> Function(String, bool)? save,
    List<Map<String, dynamic>>? products,
  }) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: QuickBrowse(
            products: products ?? [product('a'), product('b', photos: 1)],
            savedIds: const {},
            imageUrl: (s) => s,
            onSave: save ?? (_, value) async {},
            onAddToCart: cart ?? (_, size) async {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('photo swipes stay inside image area and dots follow', (
    tester,
  ) async {
    await mount(tester);
    final photos = find.byKey(const ValueKey('photos-a'));
    await tester.drag(photos, const Offset(-350, 0));
    await tester.pumpAndSettle();
    expect(tester.widget<PageView>(photos).controller!.page, 1);
    await tester.drag(find.text('Description for a'), const Offset(300, 0));
    await tester.pumpAndSettle();
    expect(tester.widget<PageView>(photos).controller!.page, 1);
    expect(find.text('Piece a'), findsOneWidget);
    expect(find.bySemanticsLabel('Photo 2 of 2'), findsOneWidget);
    await tester.drag(photos, const Offset(350, 0));
    await tester.pumpAndSettle();
    expect(tester.widget<PageView>(photos).controller!.page, 0);
  });

  testWidgets('size validation and add use the selected product and size', (
    tester,
  ) async {
    String? added;
    await mount(tester, cart: (id, size) async => added = '$id:$size');
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton).first).onPressed,
      isNull,
    );
    expect(
      tester
          .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'M').first)
          .onSelected,
      isNull,
    );
    await tester.tap(find.widgetWithText(ChoiceChip, 'S').first);
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Add to Cart').first);
    await tester.pumpAndSettle();
    expect(added, 'a:S');
  });

  testWidgets(
    'continuous browse keeps nearby selections separate and single image hides dots',
    (tester) async {
      await mount(tester);
      await tester.tap(find.widgetWithText(ChoiceChip, 'S').first);
      await tester.drag(
        find.byKey(const ValueKey('photos-a')),
        const Offset(-350, 0),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Piece b'));
      await tester.pumpAndSettle();
      expect(find.text('Piece b'), findsOneWidget);
      expect(find.bySemanticsLabel('Photo 1 of 1'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(find.descendant(
                of: find.byKey(const ValueKey('details-b')),
                matching: find.byType(FilledButton)))
            .onPressed,
        isNull,
      );
      await tester.ensureVisible(find.byKey(const ValueKey('photos-a')));
      await tester.pumpAndSettle();
      final returnedPhotos = find.byKey(const ValueKey('photos-a'));
      expect(tester.widget<PageView>(returnedPhotos).controller!.page, 1);
      expect(
          tester
              .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'S').first)
              .selected,
          isTrue);
    },
  );

  testWidgets('double tap saves and cart errors retain selection', (
    tester,
  ) async {
    bool saved = false;
    await mount(
      tester,
      save: (_, value) async => saved = value,
      cart: (_, size) async => throw Exception('Size S is sold out'),
    );
    final photos = find.byKey(const ValueKey('photos-a'));
    await tester.tap(photos);
    await tester.pump(const Duration(milliseconds: 70));
    await tester.tap(photos);
    await tester.pumpAndSettle();
    expect(saved, isTrue);
    await tester.tap(find.widgetWithText(ChoiceChip, 'S').first);
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Add to Cart').first);
    await tester.pumpAndSettle();
    expect(find.text('Size S is sold out'), findsOneWidget);
    expect(
      tester
          .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'S').first)
          .selected,
      isTrue,
    );
  });
}
