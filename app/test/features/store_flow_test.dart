import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:dress_to_impress/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

final piece = <String, dynamic>{
  'id': 'hm:demo:blue',
  'retailer': 'hm',
  'brand': 'H&M',
  'name': 'Blue cotton tee',
  'price_usd': 20,
  'sale_price_usd': 15,
  'image_url': '',
  'images': [],
  'description': 'Retailer description',
  'in_stock': true,
  'sizes': [
    {'name': 'M', 'in_stock': true},
    {'name': 'L', 'in_stock': false}
  ],
};
Map<String, dynamic> cartJson({bool filled = false}) => {
      'user_id': 'u_demo',
      'count': filled ? 1 : 0,
      'total_usd': filled ? 15 : 0,
      'groups': filled
          ? [
              {
                'retailer': 'hm',
                'subtotal_usd': 15,
                'items': [
                  {
                    'product_id': piece['id'],
                    'size': 'M',
                    'qty': 1,
                    'product': piece
                  }
                ]
              }
            ]
          : [],
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'Home -> Quick Browse -> save/cart uses shared routes, never swipe',
      (tester) async {
    tester.view.physicalSize = const Size(430, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final requests = <http.Request>[];
    final api = Api(client: MockClient((request) async {
      requests.add(request);
      expect(request.headers['X-DTI-Key'], 'test-only');
      Object data;
      if (request.url.path == '/feed') {
        data = [piece];
      } else if (request.url.path.endsWith('/ids')) {
        data = <String>[];
      } else if (request.url.path == '/cart/u_demo') {
        data = cartJson();
      } else if (request.method == 'PUT') {
        data = {'user_id': 'u_demo', 'product_id': piece['id'], 'saved': true};
      } else if (request.url.path == '/cart/u_demo/items') {
        expect(jsonDecode(request.body),
            {'product_id': piece['id'], 'size': 'M', 'qty': 1});
        data = cartJson(filled: true);
      } else {
        throw StateError('Unexpected route ${request.url.path}');
      }
      return http.Response(jsonEncode(data), 200);
    }))
      ..settings = const Settings(
          baseUrl: 'https://api.example.test', apiKey: 'test-only');
    SharedPreferences.setMockInitialValues({});
    await const ShopperProfile(completed: true, usualSize: 'M').save('u_demo');
    final store = StoreController(api: api, demo: false);
    await tester.pumpWidget(NicheApp(store: store));
    await tester.pumpAndSettle();
    expect(find.text('Suggested for you'), findsOneWidget);
    await tester.tap(find.byKey(ValueKey('suggested-${piece['id']}')));
    await tester.pumpAndSettle();
    expect(find.text('Retailer description'), findsOneWidget);
    await tester.drag(find.text('Retailer description'), const Offset(-200, 0));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Save item'));
    await tester.pumpAndSettle();
    expect(store.saved, contains(piece['id']));
    expect(find.widgetWithText(ChoiceChip, 'M'), findsNothing);
    await tester.tap(find.widgetWithText(FilledButton, 'Add to Cart'));
    await tester.pumpAndSettle();
    expect(store.cart.count, 1);
    await tester.tap(find.byTooltip('Your cart'));
    await tester.pumpAndSettle();
    expect(find.text('Size M · Qty 1'), findsOneWidget);
    expect(find.text('Total \$15.00'), findsOneWidget);
    expect(requests.any((r) => r.url.path == '/swipe'), isFalse);
    expect(requests.where((r) => r.method == 'PUT').single.url.path,
        contains('/wishlist/u_demo/items/'));
  });

  test('checkout 409 retains cart and exposes unavailable product/size',
      () async {
    final api = Api(client: MockClient((request) async {
      if (request.url.path == '/feed') {
        return http.Response(jsonEncode([piece]), 200);
      }
      if (request.url.path.endsWith('/ids')) return http.Response('[]', 200);
      if (request.url.path == '/cart/u_demo') {
        return http.Response(jsonEncode(cartJson(filled: true)), 200);
      }
      return http.Response(
          jsonEncode({
            'detail': {
              'message': 'Size M is sold out',
              'unavailable': [
                {'product_id': piece['id'], 'size': 'M'}
              ]
            }
          }),
          409);
    }));
    final store = StoreController(api: api, demo: false);
    await store.load();
    try {
      await store.checkout();
      fail('Expected stock failure');
    } on ApiError catch (e) {
      expect(e.message, 'Size M is sold out');
      expect(e.unavailable.single.size, 'M');
    }
    expect(store.cart.count, 1);
  });

  test('partial account failure leaves feed visible and prevents unsafe writes',
      () async {
    var writes = 0;
    final api = Api(client: MockClient((request) async {
      if (request.method != 'GET') writes++;
      return request.url.path == '/feed'
          ? http.Response(jsonEncode([piece]), 200)
          : http.Response('{}', 500);
    }));
    final store = StoreController(api: api, demo: false);
    await store.load();
    expect(store.feed.length, 1);
    expect(store.error, isNull);
    expect(store.accountWarning, isNotNull);
    await expectLater(store.save(piece['id'] as String, true), throwsException);
    await expectLater(store.add(piece['id'] as String, 'M'), throwsException);
    expect(writes, 0);
  });

  test('live image URLs use proxy with intact original query', () {
    final store = StoreController(
        api: Api()
          ..settings = const Settings(baseUrl: 'https://api.example.test'),
        demo: false);
    const source = 'https://image.hm.com/photo.jpg?imwidth=657&v=2';
    final uri = Uri.parse(store.imageUrl(source));
    expect(uri.path, '/img');
    expect(uri.queryParameters['url'], source);
    expect(store.imageUrl('/static/tryon/test.jpg'),
        'https://api.example.test/static/tryon/test.jpg');
  });
}
