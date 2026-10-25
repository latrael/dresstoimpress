import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/main.dart';
import 'package:dress_to_impress/features/profile/onboarding_screen.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';
import 'package:dress_to_impress/features/feed/quick_browse.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/features/fits/fits_screen.dart';
import 'package:dress_to_impress/features/profile/measurement_picker.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';

http.Response response(Object data) => http.Response(jsonEncode(data), 200);
Map<String, dynamic> fit() => {
      'id': 'f1',
      'name': 'Class fit',
      'reason': 'Easy layers',
      'pieces': [
        {
          'slot': 'top',
          'source': 'closet',
          'closet_item': {
            'id': 'c1',
            'user_id': 'u_demo',
            'category': 'top',
            'label': 'My shirt'
          }
        },
        {
          'slot': 'bottom',
          'source': 'catalog',
          'your_size': 'M',
          'in_your_size': true,
          'product': {
            'id': 'p1',
            'retailer': 'hm',
            'name': 'New jeans',
            'price_usd': 25,
            'image_url': '',
            'sizes': []
          }
        }
      ],
      'new_total_usd': 25,
      'closet_count': 1
    };
void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('style chips and own words persist together', (t) async {
    await t.pumpWidget(MaterialApp(
        home: OnboardingScreen(api: Api(), demo: true, onSaved: () async {})));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(FilterChip, 'y2k'));
    await t.pump();
    await t.tap(find.widgetWithText(FilterChip, 'gorpcore'));
    await t.pump();
    await t.ensureVisible(
        find.widgetWithText(TextField, 'Type your own (optional)'));
    await t.pumpAndSettle();
    await t.enterText(
        find.widgetWithText(TextField, 'Type your own (optional)'),
        'earth tones');
    await t.scrollUntilVisible(find.text('Save preferences'), 250,
        scrollable: find.byType(Scrollable).first);
    await t.pumpAndSettle();
    await t.tap(find.text('Save preferences'));
    await t.pumpAndSettle();
    expect((await ShopperProfile.load('u_demo')).style,
        'y2k, gorpcore, earth tones');
  });
  testWidgets(
      'inline connection failure is visible and retry keeps scan height',
      (t) async {
    var connected = false;
    await t.pumpWidget(MaterialApp(
        home: OnboardingScreen(
            api: Api(),
            demo: true,
            initialStep: 3,
            onSaved: () async {},
            onConnect: () async => connected)));
    await t.pumpAndSettle();
    t
        .widget<MeasurementPicker>(find.byWidgetPredicate(
            (w) => w is MeasurementPicker && w.kind == 'Height (cm)'))
        .onChanged(180);
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Connect for a private scan'));
    await t.pumpAndSettle();
    await t.tap(find.text('Connect for a private scan'));
    await t.pumpAndSettle();
    expect(find.textContaining('Connection is not ready'), findsOneWidget);
    connected = true;
    await t.tap(find.text('Connect for a private scan'));
    await t.pumpAndSettle();
    expect(find.text('Connect for a private scan'), findsNothing);
    expect(
        t
            .widget<MeasurementPicker>(find.byWidgetPredicate(
                (w) => w is MeasurementPicker && w.kind == 'Height (cm)'))
            .value,
        180);
  });

  testWidgets(
      'top icons replace pages and repeated taps do not create extra backs',
      (t) async {
    SharedPreferences.setMockInitialValues({});
    await const ShopperProfile(completed: true, usualSize: 'M').save('u_demo');
    await t.pumpWidget(NicheApp(store: StoreController(api: Api())));
    await t.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      await t.tap(find.byTooltip('Your cart'));
      await t.pumpAndSettle();
    }
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('product-stream')), findsOneWidget);
    await t.tap(find.byTooltip('Your cart'));
    await t.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      await t.tap(find.byTooltip('User'));
      await t.pumpAndSettle();
    }
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('product-stream')), findsOneWidget);
  });
  testWidgets('full retailer description stays behind More', (t) async {
    const full = 'A short description. More details from the retailer.';
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: QuickBrowse(
                products: const [
          {
            'id': 'p',
            'name': 'Piece',
            'price_usd': 20,
            'images': [],
            'description': 'A short description.',
            'full_description': full,
            'sizes': []
          }
        ],
                savedIds: const {},
                onSave: (_, __) async {},
                onAddToCart: (_, __) async {},
                imageUrl: (v) => v))));
    await t.pumpAndSettle();
    expect(find.text(full), findsNothing);
    await t.ensureVisible(find.text('More'));
    await t.pumpAndSettle();
    await t.tap(find.text('More'));
    await t.pumpAndSettle();
    expect(find.text(full), findsOneWidget);
    await t.tap(find.text('Less'));
    await t.pumpAndSettle();
    expect(find.text(full), findsNothing);
  });

  testWidgets('height wheel shows US units and returns metric only on Done',
      (t) async {
    double? chosen;
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: MeasurementPicker(
                kind: 'Height (cm)',
                value: 177.8,
                onChanged: (v) => chosen = v))));
    expect(find.text('5 ft 10 in'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('measure-Height (cm)')));
    await t.pumpAndSettle();
    expect(find.byType(CupertinoPicker), findsOneWidget);
    expect(chosen, isNull);
    await t.tap(find.text('Done'));
    await t.pumpAndSettle();
    expect(chosen, closeTo(177.8, .001));
    expect(t.takeException(), isNull);
  });
  testWidgets(
      'weight wheel converts pounds and Clear preserves optional omission',
      (t) async {
    double? chosen = 90;
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: MeasurementPicker(
                kind: 'Weight (kg)',
                value: 90.718474,
                onChanged: (v) => chosen = v))));
    expect(find.text('200 lb'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('measure-Weight (kg)')));
    await t.pumpAndSettle();
    await t.tap(find.text('Done'));
    await t.pumpAndSettle();
    expect(chosen, closeTo(90.718474, .0001));
    await t.tap(find.byKey(const ValueKey('measure-Weight (kg)')));
    await t.pumpAndSettle();
    await t.tap(find.text('Clear'));
    await t.pumpAndSettle();
    expect(chosen, isNull);
  });
  testWidgets(
      'Fit Creator labels owned pieces, seeds catalog taps and adds only through fit route',
      (t) async {
    final calls = <String>[];
    String? opened;
    final api = Api(client: MockClient((r) async {
      calls.add('${r.method} ${r.url.path}');
      if (r.url.path == '/fits/create') {
        expect(jsonDecode(r.body)['occasion'], 'class');
        return response({
          'fits': [fit()]
        });
      }
      if (r.url.path == '/fits/f1/cart' || r.url.path == '/cart/u_demo') {
        return response({
          'user_id': 'u_demo',
          'groups': [],
          'unavailable': [],
          'count': 0,
          'total_usd': 0
        });
      }
      throw StateError('Unexpected ${r.url.path}');
    }));
    await t.pumpWidget(MaterialApp(
        home: FitsScreen(
            store: StoreController(api: api, demo: false),
            onProduct: (p) => opened = p.id)));
    await t.tap(find.text('class'));
    await t.tap(find.text('Create 3 fits'));
    await t.pumpAndSettle();
    expect(find.text('In your closet'), findsOneWidget);
    expect(
        find.text('1 from your closet · New pieces \$25.00'), findsOneWidget);
    await t.tap(find.text('New jeans'));
    expect(opened, 'p1');
    await t.ensureVisible(find.text('Add fit to cart'));
    await t.pumpAndSettle();
    await t.tap(find.text('Add fit to cart'));
    await t.pumpAndSettle();
    expect(calls, contains('POST /fits/f1/cart'));
    expect(calls.any((c) => c.contains('/cart/u_demo/items')), false);
    expect(find.text('New pieces added. Review sizes in your cart.'),
        findsOneWidget);
  });
  testWidgets('Fit Creator exposes server failure and lets user retry',
      (t) async {
    var tries = 0;
    final api = Api(client: MockClient((r) async {
      if (++tries == 1) {
        return http.Response(
            '{"detail":"Outfit creation unavailable. Try again."}', 502);
      }
      return response({
        'fits': [fit()]
      });
    }));
    await t.pumpWidget(MaterialApp(
        home: FitsScreen(
            store: StoreController(api: api, demo: false), onProduct: (_) {})));
    await t.tap(find.text('Create 3 fits'));
    await t.pumpAndSettle();
    expect(find.textContaining('unavailable'), findsOneWidget);
    await t.tap(find.text('Create 3 fits'));
    await t.pumpAndSettle();
    expect(find.text('Class fit'), findsOneWidget);
    expect(tries, 2);
  });
}
