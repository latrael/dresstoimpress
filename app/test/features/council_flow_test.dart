import 'package:dress_to_impress/features/feed/reels_browse.dart';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:dress_to_impress/features/profile/measurement_picker.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/main.dart';
import 'package:dress_to_impress/features/discover/discover_screen.dart';
import 'package:dress_to_impress/features/profile/onboarding_screen.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';
import 'package:dress_to_impress/features/shared/pick_photo.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:dress_to_impress/features/store/cart_screen.dart';

Map<String, dynamic> product(String id) => {
      'id': id,
      'name': 'Piece $id',
      'retailer': 'hm',
      'price_usd': 20,
      'image_url': '',
      'in_stock': true,
      'sizes': [
        {'name': 'M', 'in_stock': true}
      ],
      'category': 'top'
    };
http.Response json(Object data) => http.Response(jsonEncode(data), 200);
Api api(Future<http.Response> Function(http.Request) fn) =>
    Api(client: MockClient(fn));
Uint8List photo() => base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==');
Future<void> mount(WidgetTester t, Widget child) async {
  t.view.physicalSize = const Size(430, 1100);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: child));
  await t.pumpAndSettle();
}

Future<void> tap(WidgetTester t, String text) async {
  await t.ensureVisible(find.text(text).last);
  await t.pumpAndSettle();
  await t.tap(find.text(text).last);
  await t.pumpAndSettle();
}

class FixtureStore extends StoreController {
  FixtureStore() : super(api: Api());
  @override
  Future<void> load() async {
    feed = [
      RankedProduct.fromJson(product('a')),
      RankedProduct.fromJson(product('b'))
    ];
    notifyListeners();
  }
}

class RetryProfileStore extends FixtureStore {
  int attempts = 0;
  @override
  Future<void> loadProfile({bool fromServer = false}) async {
    if (++attempts == 1) throw Exception('Temporary connection failure');
    profile = const ShopperProfile(completed: true, usualSize: 'M');
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('profile retry recovers without returning a Future from setState',
      (t) async {
    final store = RetryProfileStore();
    await t.pumpWidget(NicheApp(store: store));
    await t.pumpAndSettle();
    await t.tap(find.text('Could not load your profile. Retry'));
    await t.pumpAndSettle();
    expect(store.attempts, 2);
    expect(t.takeException(), isNull);
    expect(find.text('New account'), findsOneWidget);
  });
  testWidgets(
      'Discover separates catalog from owned pieces and opens the selected product',
      (t) async {
    String? opened;
    final client = api((r) async {
      if (r.url.path == '/search/styles') {
        return json({
          'styles': [
            {'tag': 'y2k', 'count': 42}
          ],
          'trending': [product('hot')]
        });
      }
      expect(r.url.path, '/search');
      expect(r.url.queryParameters['q'], 'jeans');
      return json({
        'query': 'jeans',
        'similar': [product('match')],
        'goes_with': [
          product('pair'),
          {
            'id': 'owned',
            'user_id': 'u_demo',
            'category': 'top',
            'label': 'My jacket',
            'from_closet': true
          }
        ]
      });
    });
    await mount(
        t,
        Scaffold(
            body: DiscoverScreen(
                store: StoreController(api: client, demo: false),
                onOpen: (p) => opened = p.id)));
    expect(find.text('y2k'), findsOneWidget);
    await t.enterText(find.byType(TextField), 'jeans');
    await t.tap(find.byTooltip('Search catalog'));
    await t.pumpAndSettle();
    expect(find.text('Similar items'), findsOneWidget);
    expect(find.text('Goes with it'), findsOneWidget);
    expect(find.text('Already in your closet'), findsOneWidget);
    final grids = t.widgetList<ProductGrid>(find.byType(ProductGrid));
    expect(grids.expand((g) => g.products).map((p) => p.id), ['match', 'pair']);
    await t.tap(find.byKey(const ValueKey('suggested-match')));
    expect(opened, 'match');
  });
  testWidgets('photo search uploads privately to search, never posts to Inspo',
      (t) async {
    final routes = <String>[];
    final client = api((r) async {
      routes.add(r.url.path);
      if (r.url.path == '/search/styles') {
        return json({'styles': [], 'trending': []});
      }
      expect(r.url.path, '/search/photo');
      expect(latin1.decode(r.bodyBytes), contains('image/png'));
      return json({
        'photo_url': '/static/search.png',
        'tags': [],
        'similar': [product('camera')],
        'goes_with': []
      });
    });
    await mount(
        t,
        Scaffold(
            body: DiscoverScreen(
                store: StoreController(api: client, demo: false),
                onOpen: (_) {},
                picker: () async => PickedPhoto(photo(), 'image/png'))));
    await t.tap(find.byTooltip('Search with a photo'));
    await t.pumpAndSettle();
    expect(find.text('Piece camera'), findsOneWidget);
    expect(routes, contains('/search/photo'));
    expect(
        routes.any((r) => r.contains('fitcheck') || r.contains('body-photo')),
        false);
  });
  testWidgets('Liked includes saved products outside the currently loaded feed',
      (t) async {
    final client = api((r) async {
      expect(r.url.path, '/wishlist/u_demo');
      return json([product('outside')]);
    });
    final store = StoreController(api: client, demo: false)
      ..feed = [RankedProduct.fromJson(product('inside'))];
    String? opened;
    await mount(t, LikedScreen(store: store, onOpen: (p) => opened = p.id));
    expect(find.text('Piece outside'), findsOneWidget);
    expect(find.text('Piece inside'), findsNothing);
    await t.tap(find.byKey(const ValueKey('suggested-outside')));
    expect(opened, 'outside');
  });
  testWidgets('the × on a Liked tile removes it from the wishlist', (t) async {
    final deleted = <String>[];
    final client = api((r) async {
      if (r.method == 'DELETE') {
        deleted.add(r.url.path);
        return json({'user_id': 'u_demo', 'product_id': 'one', 'saved': false});
      }
      return json([product('one'), product('two')]);
    });
    final store = StoreController(api: client, demo: false);
    await mount(t, LikedScreen(store: store, onOpen: (_) {}));
    expect(find.text('Piece one'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('remove-liked-one')));
    await t.pumpAndSettle();
    expect(deleted, ['/wishlist/u_demo/items/one']);
    expect(find.text('Piece one'), findsNothing);
    expect(find.text('Piece two'), findsOneWidget);
    expect(deleted, ['/wishlist/u_demo/items/one']);
  });
  testWidgets(
      'four header icons persist across Home, cart and User; logout returns to Login',
      (t) async {
    await const ShopperProfile(completed: true, usualSize: 'M').save('u_demo');
    await t.pumpWidget(NicheApp(store: StoreController(api: Api())));
    await t.pumpAndSettle();
    void icons() {
      for (final label in ['Liked', 'Your cart', 'Closet', 'User']) {
        expect(find.byTooltip(label), findsOneWidget);
      }
    }

    icons();
    expect(find.byKey(const ValueKey('tab-2')), findsOneWidget);
    await t.tap(find.byTooltip('Your cart'));
    await t.pumpAndSettle();
    icons();
    await t.tap(find.byTooltip('User'));
    await t.pumpAndSettle();
    icons();
    expect(find.text('Measurements & size'), findsOneWidget);
    await t.scrollUntilVisible(find.text('Log out on this device'), 200,
        scrollable: find.byType(Scrollable).first);
    await tap(t, 'Log out on this device');
    expect(find.text('Login'), findsOneWidget);
    await tap(t, 'Login');
    expect(find.byKey(const ValueKey('product-stream')), findsOneWidget);
  });
  testWidgets('Discover item tap uses the same seeded Home landing', (t) async {
    await const ShopperProfile(completed: true, usualSize: 'M').save('u_demo');
    final store = FixtureStore();
    await t.pumpWidget(NicheApp(store: store));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('tab-1')));
    await t.pumpAndSettle();
    final selected = store.feed.first;
    await t.enterText(find.byType(TextField), selected.product.name);
    await t.tap(find.byTooltip('Search catalog'));
    await t.pumpAndSettle();
    await t
        .ensureVisible(find.byKey(ValueKey('suggested-${selected.id}')).first);
    await t.pumpAndSettle();
    await t.tap(find.byKey(ValueKey('suggested-${selected.id}')).first);
    await t.pumpAndSettle();
    expect(find.text('Similar to: ${selected.product.name}'), findsOneWidget);
    expect(t.widget<ReelsBrowse>(find.byType(ReelsBrowse)).products.first['id'],
        selected.id);
    await t.tap(find.byTooltip('Show all products'));
    await t.pumpAndSettle();
    expect(find.text('Similar to: ${selected.product.name}'), findsNothing);
  });
  testWidgets(
      'scan estimates are reviewed, editable, and saved only through the review action',
      (t) async {
    var saved = false;
    Map<String, dynamic>? confirmed;
    final client = api((r) async {
      if (r.method == 'GET') {
        return json({'id': 'u_demo', 'display_name': 'Demo'});
      }
      if (r.url.path.endsWith('/body-scan')) {
        expect(r.url.queryParameters['commit'], 'false');
        return json({
          'committed': false,
          'body_photo_url': '/static/body.png',
          'body_profile': {
            'height_cm': 180,
            'weight_kg': 75,
            'chest_in': 40,
            'waist_in': 32,
            'hip_in': 38,
            'inseam_in': 31,
            'source': 'ai',
            'full_body': true,
            'note': 'Review your fit.'
          }
        });
      }
      if (r.url.path.endsWith('/body-scan/confirm')) {
        confirmed = jsonDecode(r.body) as Map<String, dynamic>;
        return json({
          'committed': true,
          'body_photo_url': '/static/body.png',
          'body_profile': confirmed!['profile']
        });
      }
      if (r.url.path.endsWith('/body-profile')) {
        expect(jsonDecode(r.body), isNot(contains('chest_cm')));
        expect(jsonDecode(r.body), isNot(contains('waist_cm')));
        return json({'height_cm': 180, 'weight_kg': 75});
      }
      return json({'id': 'u_demo', 'display_name': 'Demo'});
    });
    await mount(
        t,
        OnboardingScreen(
            api: client,
            initialStep: 3,
            onSaved: () async {
              saved = true;
            },
            picker: () async => PickedPhoto(photo(), 'image/png')));
    t
        .widget<MeasurementPicker>(find.byWidgetPredicate(
            (w) => w is MeasurementPicker && w.kind == 'Height (cm)'))
        .onChanged(180);
    await t.pumpAndSettle();
    t
        .widget<MeasurementPicker>(find.byWidgetPredicate(
            (w) => w is MeasurementPicker && w.kind == 'Weight (kg)'))
        .onChanged(75);
    await t.pumpAndSettle();
    await tap(t, 'Choose a full-body photo');
    expect(saved, false);
    expect(confirmed, isNull);
    await tap(t, 'Review measurements');
    expect(
        t
            .widget<MeasurementPicker>(find.byWidgetPredicate(
                (w) => w is MeasurementPicker && w.kind == 'Chest (cm)'))
            .value,
        closeTo(101.6, .01));
    t
        .widget<MeasurementPicker>(find.byWidgetPredicate(
            (w) => w is MeasurementPicker && w.kind == 'Waist (cm)'))
        .onChanged(80);
    await t.pumpAndSettle();
    await t.scrollUntilVisible(find.text('Save preferences'), 300,
        scrollable: find.byType(Scrollable).first);
    await tap(t, 'Save preferences');
    expect(saved, true);
    expect((confirmed!['profile'] as Map)['waist_in'], closeTo(80 / 2.54, .01));
    expect((confirmed!['profile'] as Map)['chest_in'], 40);
    expect(confirmed!['edited'], contains('waist_in'));
    expect(confirmed!['edited'], isNot(contains('chest_in')));
  });
  test('saved-profile sizing never fills missing measurements with defaults',
      () async {
    final client = api((r) async {
      final j = jsonDecode(r.body);
      expect(j['height_cm'], isNull);
      expect(j['weight_kg'], isNull);
      expect(j['user_id'], 'u_demo');
      return json(
          {'size': 'M', 'confidence': 'medium', 'reason': 'Saved size'});
    });
    await client.sizeAdvice('p', useSavedProfile: true);
  });
  test('missing cart line never falls back to creating another line', () async {
    final methods = <String>[];
    final client = api((r) async {
      methods.add(r.method);
      if (r.method == 'PATCH') {
        return http.Response('{"detail":"cart line not found"}', 404);
      }
      return json(
          {'user_id': 'u_demo', 'groups': [], 'count': 0, 'total_usd': 0});
    });
    final store = StoreController(api: client, demo: false);
    await expectLater(
        store.changeSize(
            const CartItem(productId: 'gone', size: 'S', qty: 1), 'M'),
        throwsStateError);
    expect(methods, ['PATCH', 'GET']);
  });
  testWidgets(
      'unavailable cart lines remain visible, removable and block checkout',
      (t) async {
    var removed = false;
    final client = api((r) async {
      if (r.method == 'DELETE') removed = true;
      return json({
        'user_id': 'u_demo',
        'groups': [],
        'total_usd': 0,
        'count': removed ? 0 : 1,
        'unavailable': removed
            ? []
            : [
                {
                  'product_id': 'gone',
                  'size': 'M',
                  'qty': 1,
                  'name': 'Gone tee',
                  'unavailable_reason': 'size sold out'
                }
              ]
      });
    });
    await mount(
        t, CartScreen(store: StoreController(api: client, demo: false)));
    expect(find.text('Gone tee'), findsOneWidget);
    expect(
        t
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Checkout in Nessie sandbox'))
            .onPressed,
        isNull);
    await t.tap(find.byTooltip('Remove unavailable Gone tee'));
    await t.pumpAndSettle();
    expect(removed, true);
    expect(find.text('Gone tee'), findsNothing);
  });
}
