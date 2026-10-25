// Adam: body-scan measurements into the shopper profile, and the partially-paid receipt.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';
import 'package:dress_to_impress/features/store/cart_screen.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const scan = BodyProfile(
    heightCm: 178,
    weightKg: 72,
    chestIn: 40,
    waistIn: 32,
    hipIn: null,
    inseamIn: 31.5,
    shoeUs: 10,
    fit: 'oversized',
    source: 'ai');

void main() {
  test(
      'withBody: a fresh scan wins, converts inches to cm, keeps what it lacks',
      () {
    const mine = ShopperProfile(
        completed: true,
        style: 'Y2K',
        usualSize: 'M',
        fit: 'regular',
        heightCm: 170,
        waistCm: 76,
        hipCm: 97,
        budgets: {'top': 40});
    final p = mine.withBody(scan);
    expect(p.heightCm, 178);
    expect(p.weightKg, 72);
    expect(p.chestCm, 101.6);
    expect(p.waistCm, 81.3);
    expect(p.hipCm, 97); // the scan had no hips; mine stays
    expect(p.inseamCm, 80.0);
    expect(p.shoeUs, 10);
    expect(p.fit, 'oversized');
    expect((p.completed, p.style, p.usualSize), (true, 'Y2K', 'M'));
    expect(p.budgets, {'top': 40});
  });

  test('withBody gapsOnly: only blank fields are filled from the server', () {
    const mine = ShopperProfile(heightCm: 170, waistCm: 76, fit: 'slim');
    final p = mine.withBody(scan, gapsOnly: true);
    expect(p.heightCm, 170);
    expect(p.waistCm, 76);
    expect(p.fit, 'slim');
    expect(p.chestCm, 101.6);
    expect(p.weightKg, 72);
    expect(p.inseamCm, 80.0);
    expect(p.hipCm, isNull);
    // A server profile with no height never writes a zero.
    const empty = BodyProfile(heightCm: 0, source: 'estimate');
    expect(const ShopperProfile().withBody(empty, gapsOnly: true).heightCm,
        isNull);
  });

  testWidgets(
      'receipt shows Paid X of Y and a Retry payment button per failed store',
      (tester) async {
    final calls = <String>[];
    final api = Api(client: MockClient((r) async {
      calls.add('${r.method} ${r.url.path}');
      if (r.url.path == '/cart/u_demo') {
        return http.Response(jsonEncode(_cart), 200);
      }
      if (r.url.path == '/checkout/u_demo') {
        return http.Response(jsonEncode(_receipt('nessie_failed')), 200);
      }
      if (r.url.path == '/orders/o_1/retry') {
        expect(r.url.queryParameters['retailer'], 'uniqlo');
        return http.Response(jsonEncode(_receipt('paid')), 200);
      }
      throw StateError('Unexpected route ${r.url.path}');
    }))
      ..settings = const Settings(
          baseUrl: 'https://api.example.test', apiKey: 'k', userId: 'u_demo');
    final store = StoreController(api: api, demo: false);
    await tester.pumpWidget(MaterialApp(home: CartScreen(store: store)));
    await tester.pumpAndSettle();
    expect(calls,
        ['GET /cart/u_demo']); // opening the cart re-reads the server copy
    expect(find.text('Total \$25.00'), findsOneWidget);
    await tester
        .tap(find.widgetWithText(FilledButton, 'Checkout'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Place order'));
    await tester.pumpAndSettle();
    expect(find.text('Order o_1'), findsOneWidget);
    expect(find.text('Paid \$15.00 of \$25.00'), findsOneWidget);
    expect(find.text('Retry payment'), findsOneWidget);
    await tester.tap(find.text('Retry payment'));
    await tester.pumpAndSettle();
    expect(calls.last, 'POST /orders/o_1/retry');
    expect(find.text('Total \$25.00'), findsOneWidget);
    expect(find.text('Retry payment'), findsNothing);
  });
}

const _cart = {
  'user_id': 'u_demo',
  'count': 2,
  'total_usd': 25,
  'groups': [
    {
      'retailer': 'hm',
      'subtotal_usd': 15,
      'items': [
        {'product_id': 'hm:1', 'size': 'M', 'qty': 1}
      ]
    },
    {
      'retailer': 'uniqlo',
      'subtotal_usd': 10,
      'items': [
        {'product_id': 'uniqlo:1', 'size': 'M', 'qty': 1}
      ]
    },
  ],
};

Map<String, Object> _receipt(String uniqloStatus) => {
      'order_id': 'o_1',
      'total_usd': 25,
      'purchases': [
        {'retailer': 'hm', 'amount_usd': 15, 'status': 'paid', 'items': []},
        {
          'retailer': 'uniqlo',
          'amount_usd': 10,
          'status': uniqloStatus,
          'items': []
        },
      ],
    };
