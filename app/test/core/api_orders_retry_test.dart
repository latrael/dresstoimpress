// Core (Adam): retrying unpaid store purchases of an order against the backend contract.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Api _api(List<http.Request> seen, Object Function(http.Request) reply, {int status = 200}) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), status, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

const _receipt = {
  'order_id': 'o_1', 'total_usd': 25, 'created_at': '2026-10-24T21:30:00+00:00',
  'purchases': [
    {'retailer': 'hm', 'amount_usd': 15, 'status': 'paid', 'nessie_id': 'n_1', 'items': [
      {'product_id': 'hm:1', 'size': 'M', 'qty': 1, 'price_usd': 15}]},
    {'retailer': 'uniqlo', 'amount_usd': 10, 'status': 'nessie_failed', 'items': []},
  ],
};

void main() {
  test('retryOrder posts /orders/{id}/retry for one retailer and parses the receipt', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _receipt);
    final res = await api.retryOrder('o_1', retailer: 'uniqlo');
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/orders/o_1/retry'));
    expect(r.url.queryParameters, {'user_id': 'u_demo', 'retailer': 'uniqlo'});
    expect(res.orderId, 'o_1');
    expect(res.totalUsd, 25);
    expect(res.purchases.map((p) => p.status), ['paid', 'nessie_failed']);
    expect(res.purchases.first.nessieId, 'n_1');
    expect(res.purchases.first.items.single.size, 'M');
  });

  test('retryOrder without a retailer retries every unpaid store', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _receipt);
    await api.retryOrder('o_2');
    final r = seen.single;
    expect(r.url.path, '/orders/o_2/retry');
    expect(r.url.queryParameters, {'user_id': 'u_demo'});
  });

  test('retryOrder surfaces 503 when payments are not configured', () async {
    final api = _api(<http.Request>[], (_) => {'detail': 'Payments not configured'}, status: 503);
    await expectLater(api.retryOrder('o_1'), throwsA(isA<ApiError>().having((e) => e.status, 'status', 503)));
  });
}
