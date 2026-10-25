// Core (Adam): shop the look grouped per tagged piece — Api.shopFitCheckGrouped / ShopTagGroup.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Api _api(List<http.Request> seen, Object Function(http.Request) reply) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

const _jeans = {
  'id': 'hm:1', 'retailer': 'hm', 'name': 'Baggy Jeans', 'category': 'bottom', 'price_usd': 29.99,
  'image_url': 'https://image.hm.com/j.jpg', 'in_stock': true,
  'reason': 'Light wash on your black tee', 'pairs_with': ['ci_1'], 'score': 0.8, 'matched_tag': 'baggy jeans',
};
const _tee = {
  'id': 'zara:2', 'retailer': 'zara', 'name': 'Baby Tee', 'category': 'top', 'price_usd': 15.0,
  'image_url': 'https://static.zara.net/t.jpg', 'in_stock': true,
  'reason': 'from the fit: white baby tee', 'pairs_with': [], 'score': 0.0, 'matched_tag': 'white baby tee',
};

const _grouped = [
  {
    'tag': {'label': 'baggy jeans', 'category': 'bottom', 'color': 'light blue', 'box': [0.25, 0.5, 0.75, 0.95], 'product_id': null},
    'products': [_jeans],
  },
  {
    'tag': {'label': 'unicorn hat', 'category': 'accessory', 'color': 'pink', 'box': null, 'product_id': null},
    'products': <Object>[],
  },
  {
    'tag': {'label': 'white baby tee', 'category': 'top', 'color': 'white', 'box': null, 'product_id': 'zara:2'},
    'products': [_tee],
  },
];

void main() {
  test('shopFitCheckGrouped asks for grouped=true and keeps post order', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _grouped);
    final groups = await api.shopFitCheckGrouped('fc_1');

    expect(seen.single.method, 'GET');
    expect(seen.single.url.path, '/fitcheck/fc_1/shop');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo', 'grouped': 'true'});

    expect(groups.map((g) => g.tag.label).toList(), ['baggy jeans', 'unicorn hat', 'white baby tee']);
    expect(groups[0].tag.category, 'bottom');
    expect(groups[0].tag.box, [0.25, 0.5, 0.75, 0.95]);
    expect(groups[0].products.single.id, 'hm:1');
    expect(groups[0].products.single.reason, 'Light wash on your black tee');
    expect(groups[0].products.single.matchedTag, 'baggy jeans');
    expect(groups[0].products.single.product.name, 'Baggy Jeans');
  });

  test('a tag with no match keeps its group with an empty product list', () async {
    final api = _api([], (_) => _grouped);
    final groups = await api.shopFitCheckGrouped('fc_1');
    expect(groups[1].isEmpty, isTrue);
    expect(groups[1].products, isEmpty);
    expect(groups[1].tag.label, 'unicorn hat');
    expect(groups[1].tag.box, isNull);
    expect(groups[2].tag.productId, 'zara:2');
    expect(groups[2].products.single.score, 0.0);
  });

  test('ShopTagGroup.fromJson tolerates a missing products key', () {
    final g = ShopTagGroup.fromJson({'tag': {'label': 'cap'}});
    expect(g.tag.label, 'cap');
    expect(g.products, isEmpty);
  });

  test('flat shopFitCheck is unchanged (no grouped flag)', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => [_jeans, _tee]);
    final flat = await api.shopFitCheck('fc_1');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo'});
    expect(flat.map((p) => p.id).toList(), ['hm:1', 'zara:2']);
  });
}
