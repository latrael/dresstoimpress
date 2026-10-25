import 'package:dress_to_impress/features/shared/niche_theme.dart';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/main.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:dress_to_impress/features/store/cart_screen.dart';
import 'package:dress_to_impress/features/profile/onboarding_screen.dart';
import 'package:dress_to_impress/features/profile/body_scan_screen.dart';
import 'package:dress_to_impress/features/shared/pick_photo.dart';

http.Response reply(Object value) => http.Response(jsonEncode(value), 200);
Map<String, dynamic> piece() => {
      'id': 'p',
      'name': 'Seed piece',
      'retailer': 'kith',
      'price_usd': 20,
      'image_url': '',
      'in_stock': true,
      'your_size': 'M',
      'in_your_size': true,
      'sizes': [
        {'name': 'M', 'in_stock': true}
      ]
    };

class FeedFixture extends StoreController {
  FeedFixture(Api client) : super(api: client, demo: false);
  @override
  Future<void> load() async {
    feed = [RankedProduct.fromJson(piece())];
    notifyListeners();
  }
}

Future<void> mount(WidgetTester t, Widget child) async {
  t.view.physicalSize = const Size(430, 1000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: child));
  await t.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('Shop-for loads server choice and persists a changed choice',
      (t) async {
    Map<String, dynamic>? update;
    final client = Api(client: MockClient((r) async {
      if (r.method == 'PATCH' && r.url.path == '/users/u_demo') {
        update = jsonDecode(r.body) as Map<String, dynamic>;
      }
      if (r.url.path.endsWith('body-profile')) {
        return reply({'height_cm': 0, 'source': 'manual'});
      }
      if (r.url.path == '/onboarding') {
        return reply({
          'user': {'id': 'u_demo', 'display_name': 'Demo'},
          'styles': [],
          'budgets': {},
          'unmatched': []
        });
      }
      return reply({
        'id': 'u_demo',
        'display_name': 'Demo',
        'shop_for': 'men',
        'body_profile': {'height_cm': 180, 'chest_in': 40, 'source': 'ai'}
      });
    }));
    await mount(
        t, OnboardingScreen(api: client, initialStep: 7, onSaved: () async {}));
    expect(t.widget<NicheChip>(find.widgetWithText(NicheChip, 'Men')).selected,
        true);
    await t.tap(find.widgetWithText(NicheChip, 'Women'));
    await t.tap(find.text('Save preferences'));
    await t.pumpAndSettle();
    expect(update!['shop_for'], 'women');
  });
  testWidgets(
      'all eight store choices retain known retailer IDs as preferences',
      (t) async {
    final client = Api(
        client: MockClient((r) async => reply({
              'id': 'u_demo',
              'display_name': 'Demo',
              'preferred_stores': ['princesspolly', 'kith'],
              'shop_for': 'both'
            })));
    final store = StoreController(api: client, demo: false);
    await store.loadProfile(fromServer: true);
    expect(store.profile.preferredStores, ['princesspolly', 'kith']);
    expect(store.profile.otherStores, '');
    await mount(
        t, OnboardingScreen(api: client, initialStep: 2, onSaved: () async {}));
    expect(find.byType(NicheChip), findsNWidgets(8));
    expect(
        t
            .widget<NicheChip>(find.widgetWithText(NicheChip, 'Princess Polly'))
            .selected,
        true);
    expect(find.text('We currently carry H&M and Uniqlo.'), findsNothing);
  });
  testWidgets('seeded refresh excludes a shown seed and a new tap resets it',
      (t) async {
    final requests = <String?>[];
    final client = Api(client: MockClient((r) async {
      if (r.url.path == '/search/styles') {
        return reply({'styles': [], 'trending': []});
      }
      if (r.url.path == '/discover/board') {
        // Discover is a board now: the product tile opens Home seeded with it, like the old grid did
        return reply({
          'styles': [],
          'items': [
            {'kind': 'product', 'product': piece()}
          ],
          'next_offset': null
        });
      }
      if (r.url.path.endsWith('/tryons')) {
        return reply({
          'p': {'status': 'needs_photo'}
        });
      }
      expect(r.url.path, '/feed');
      expect(r.url.queryParameters['seed'], 'p');
      requests.add(r.url.queryParameters['seed_shown']);
      return reply([piece()]);
    }));
    await mount(t, ShopShell(store: FeedFixture(client)));
    Future<void> choose() async {
      await t.tap(find.byKey(const ValueKey('tab-1')));
      await t.pumpAndSettle();
      await t.ensureVisible(find.byKey(const ValueKey('board-product-p')));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('board-product-p')));
      await t.pumpAndSettle();
    }

    await choose();
    await t.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    await t.pumpAndSettle();
    await t.tap(find.byTooltip('Show all products'));
    await t.pumpAndSettle();
    await choose();
    expect(requests, [null, 'true', null]);
  });
  testWidgets(
      'unavailable cart line keeps its saved image and retailer heading is readable',
      (t) async {
    const image = 'https://cdn.shopify.com/removed.jpg';
    final client = Api(
        client: MockClient((r) async => reply({
              'user_id': 'u_demo',
              'count': 2,
              'total_usd': 20,
              'groups': [
                {
                  'retailer': 'princesspolly',
                  'subtotal_usd': 20,
                  'items': [
                    {
                      'product_id': 'p',
                      'size': 'M',
                      'qty': 1,
                      'image_url': image
                    }
                  ]
                }
              ],
              'unavailable': [
                {
                  'product_id': 'gone',
                  'size': 'M',
                  'qty': 1,
                  'name': 'Removed piece',
                  'reason': 'no longer available',
                  'image_url': image
                }
              ]
            })));
    await mount(
        t, CartScreen(store: StoreController(api: client, demo: false)));
    expect(find.text('Princess Polly'), findsOneWidget);
    final row =
        t.widget<ListTile>(find.widgetWithText(ListTile, 'Removed piece'));
    expect(row.leading, isNotNull);
    expect(
        t.widget<Image>(find.byType(Image).first).image, isA<NetworkImage>());
  });
  testWidgets('canceling standalone scan never confirms the draft', (t) async {
    final calls = <String>[];
    final client = Api(client: MockClient((r) async {
      calls.add(r.url.path);
      expect(r.url.queryParameters['commit'], 'false');
      return reply({
        'committed': false,
        'body_photo_url': '/static/uploads/draft.png',
        'body_profile': {
          'height_cm': 180,
          'weight_kg': 75,
          'chest_in': 40,
          'source': 'ai'
        }
      });
    }));
    await mount(
        t,
        Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => BodyScanScreen(
                                api: client,
                                heightCm: 180,
                                weightKg: 75,
                                picker: () async => PickedPhoto(
                                    Uint8List.fromList([1, 2, 3]),
                                    'image/png')))),
                    child: const Text('Scan')))));
    await t.tap(find.text('Scan'));
    await t.pumpAndSettle();
    await t.tap(find.text('Choose full-body photo'));
    await t.pumpAndSettle();
    expect(find.text('Confirm these measurements'), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(calls, ['/users/u_demo/body-scan']);
  });
}
