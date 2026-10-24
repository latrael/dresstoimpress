import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/main.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';
import 'package:dress_to_impress/features/profile/onboarding_screen.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:dress_to_impress/features/store/cart_screen.dart';
import 'package:dress_to_impress/features/feed/quick_browse.dart';

const garment = Product(
    id: 'tee',
    retailer: 'hm',
    name: 'Test tee',
    priceUsd: 20,
    sizes: [
      ProductSize(name: 'S', inStock: true),
      ProductSize(name: 'M', inStock: true)
    ],
    imageUrl: '');
void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets(
      'first visit opens onboarding; skip persists and next launch browses',
      (tester) async {
    tester.view.physicalSize = const Size(430, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final store = StoreController(api: Api(), demo: true);
    await tester.pumpWidget(NicheApp(store: store));
    await tester.pumpAndSettle();
    expect(find.text('Welcome to Niche'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Skip for now'), 500,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('Skip for now'));
    await tester.pumpAndSettle();
    expect(find.text('Suggested for you'), findsOneWidget);
    expect((await ShopperProfile.load('u_demo')).completed, true);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(NicheApp(store: StoreController(api: Api())));
    await tester.pumpAndSettle();
    expect(find.text('Welcome to Niche'), findsNothing);
    expect(find.text('Suggested for you'), findsOneWidget);
  });
  test(
      'automatic sizing uses explicit dimensions, converts waist and caches per profile',
      () async {
    var calls = 0;
    final api = Api(client: MockClient((r) async {
      calls++;
      expect(r.url.path, '/size');
      final j = jsonDecode(r.body);
      expect(j['height_cm'], 181);
      expect(j['weight_kg'], 78);
      expect(j['waist_in'], closeTo(32, .01));
      expect(j['fit'], 'oversized');
      return http.Response(
          jsonEncode(
              {'size': 'M', 'confidence': 'medium', 'reason': 'Measured fit'}),
          200);
    }))
      ..settings = const Settings();
    final store = StoreController(api: api, demo: false)
      ..feed = [const RankedProduct(product: garment)];
    await const ShopperProfile(
            completed: true,
            heightCm: 181,
            weightKg: 78,
            waistCm: 81.28,
            fit: 'oversized')
        .save('u_demo');
    await store.loadProfile();
    expect(await store.automaticSize('tee'), 'M');
    expect(await store.automaticSize('tee'), 'M');
    expect(calls, 1);
  });
  test('skipped measurements never use default body dimensions or guess size',
      () async {
    var calls = 0;
    final api = Api(client: MockClient((r) async {
      calls++;
      throw StateError('No sizing request expected');
    }));
    final store = StoreController(api: api, demo: false)
      ..feed = [const RankedProduct(product: garment)];
    await store.loadProfile();
    expect(await store.automaticSize('tee'), isNull);
    expect(calls, 0);
  });
  testWidgets('automatic browse adds recommended size with no size chooser',
      (tester) async {
    String? added;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: QuickBrowse(
                products: [browseMap(const RankedProduct(product: garment))],
                savedIds: const {},
                imageUrl: (s) => s,
                automaticSizing: true,
                onSizeAdvice: (_) async => 'M',
                onSave: (_, v) async {},
                onAddToCart: (id, size) async {
                  added = '$id:$size';
                }))));
    await tester.pumpAndSettle();
    expect(find.byType(ChoiceChip), findsNothing);
    expect(find.text('Find my size'), findsNothing);
    await tester.ensureVisible(find.text('Add to Cart'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add to Cart'));
    await tester.pumpAndSettle();
    expect(added, 'tee:M');
  });
  testWidgets('cart pencil changes size and preserves quantity and total',
      (tester) async {
    final store = StoreController(api: Api())
      ..feed = [const RankedProduct(product: garment)];
    await store.add('tee', 'S');
    await store.add('tee', 'S');
    await tester.pumpWidget(MaterialApp(home: CartScreen(store: store)));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Edit size for Test tee'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, 'M'));
    await tester.pumpAndSettle();
    expect(store.cart.groups.single.items.single.size, 'M');
    expect(store.cart.count, 2);
    expect(store.cart.totalUsd, 40);
    expect(find.text('Size M · Qty 2'), findsOneWidget);
  });
  test('measurement profile and budgets stay scoped to the user', () async {
    await const ShopperProfile(
        completed: true,
        chestCm: 96,
        hipCm: 98,
        inseamCm: 80,
        usualSize: 'M',
        budgets: {'tops': 40}).save('ryan');
    final p = await ShopperProfile.load('ryan');
    expect(p.chestCm, 96);
    expect(p.budgets['tops'], 40);
    expect((await ShopperProfile.load('another')).completed, false);
  });
  test('failed live size replacement refreshes cart and never reports success',
      () async {
    final calls = <String>[];
    final api = Api(client: MockClient((r) async {
      calls.add(r.method);
      if (r.method == 'PATCH') return http.Response('unavailable', 409);
      if (r.method == 'POST' || r.method == 'DELETE') {
        fail('Do not fall back to add/remove after a refused size change');
      }
      return http.Response(
          jsonEncode({
            'user_id': 'u_demo',
            'count': 2,
            'total_usd': 40,
            'groups': [
              {
                'retailer': 'hm',
                'subtotal_usd': 40,
                'items': [
                  {'product_id': 'tee', 'size': 'S', 'qty': 2}
                ]
              }
            ]
          }),
          200);
    }));
    final store = StoreController(api: api, demo: false);
    await expectLater(
        store.changeSize(
            const CartItem(productId: 'tee', size: 'S', qty: 2), 'M'),
        throwsStateError);
    expect(calls, ['PATCH', 'GET']);
    expect(store.cart.groups.single.items.single.size, 'S');
    expect(store.cart.count, 2);
  });
  test(
      'unavailable recommendation is never added or replaced by an arbitrary size',
      () async {
    final api = Api(
        client: MockClient((r) async => http.Response(
            jsonEncode(
                {'size': 'XL', 'confidence': 'low', 'reason': 'Unavailable'}),
            200)));
    final store = StoreController(api: api, demo: false)
      ..feed = [const RankedProduct(product: garment)];
    store.profile =
        const ShopperProfile(completed: true, heightCm: 180, weightKg: 75);
    expect(await store.automaticSize('tee'), isNull);
    expect(store.cart.count, 0);
  });
  testWidgets(
      'onboarding accepts actual dimensions with all price fields skipped',
      (tester) async {
    var finished = false;
    await tester.pumpWidget(MaterialApp(
        home: OnboardingScreen(
            api: Api(),
            demo: true,
            firstRun: true,
            onSaved: () async {
              finished = true;
            })));
    await tester.pumpAndSettle();
    for (final e in {
      'Height (cm)': '181',
      'Weight (kg)': '78',
      'Waist (cm)': '81.28'
    }.entries) {
      final field = find.widgetWithText(TextField, e.key);
      await tester.scrollUntilVisible(field, 200,
          scrollable: find.byType(Scrollable).first);
      await tester.enterText(field, e.value);
    }
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Start browsing'), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(find.text('Start browsing'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start browsing'));
    await tester.pumpAndSettle();
    final p = await ShopperProfile.load('u_demo');
    expect(finished, true);
    expect(p.heightCm, 181);
    expect(p.weightKg, 78);
    expect(p.waistCm, 81.28);
    expect(p.budgets, isEmpty);
  });
}
