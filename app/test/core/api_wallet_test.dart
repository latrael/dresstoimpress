// The Niche Card: GET /wallet/{user} parsing and the receipt's Nessie line.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/store/cart_screen.dart' show paidLine;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('wallet parses the live account, totals and joined purchases', () async {
    final seen = <http.Request>[];
    final api = Api(client: MockClient((r) async {
      seen.add(r);
      return http.Response(
          jsonEncode({
            'live': true,
            'account': {'last4': 'd390', 'nickname': 'dti', 'type': 'Credit Card', 'balance': 5000, 'rewards': 0},
            'spent_usd': 21.99,
            'spent_month_usd': 7.99,
            'purchases': [
              {'nessie_id': 'e52275e2-858f', 'retailer': 'hm', 'store_name': 'H&M', 'amount_usd': 7.99,
               'nessie_amount': 8, 'date': '2026-10-24', 'status': 'completed', 'order_id': 'o1',
               'items': [{'name': 'Regular Fit T-shirt', 'size': 'S', 'qty': 1}]}
            ]
          }),
          200,
          headers: {'content-type': 'application/json'});
    }));
    api.settings = const Settings(baseUrl: 'https://dti.example', apiKey: 'k', userId: 'u_t');
    final w = await api.wallet();
    expect(seen.single.url.path, '/wallet/u_t');
    expect((w.live, w.account!.last4, w.spentUsd, w.spentMonthUsd), (true, 'd390', 21.99, 7.99));
    final p = w.purchases.single;
    expect((p.storeName, p.amountUsd, p.nessieAmount, p.orderId), ('H&M', 7.99, 8.0, 'o1'));
    expect(p.items, ['Regular Fit T-shirt · S']);
    expect(Wallet.fromJson({'live': false, 'account': null, 'purchases': []}).account, isNull);
  });

  test('receipt line names the Nessie purchase', () {
    Purchase p(String? id) => Purchase.fromJson({'retailer': 'hm', 'amount_usd': 8, 'items': [], 'status': 'paid',
        if (id != null) 'nessie_id': id});
    expect(paidLine(p('e52275e2-858f-44b6')), 'Paid · Nessie #e52275e2');
    expect(paidLine(p(null)), 'Paid');
  });
}
