// Core (Adam): council v2 routes. Seeded feed + size badges, Discover search / styles / photo, atomic cart
// size change, PATCH /users with stores + onboarded, Inspo author filter. Mock-client pattern from api_core_test.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> _card(String id, {String? yourSize, bool? inYourSize}) => {
      'id': id, 'retailer': 'hm', 'name': 'Piece $id', 'price_usd': 20, 'image_url': '', 'reason': 'goes with it',
      'your_size': yourSize, 'in_your_size': inYourSize,
    };

Api _api(List<http.Request> seen, Object Function(http.Request) reply, {int status = 200}) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), status, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

void main() {
  test('feed parses size badges (true / false / unknown) and sends seed only when given', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => [_card('a', yourSize: 'M', inYourSize: true), _card('b', yourSize: 'L', inYourSize: false), _card('c')]);
    final cards = await api.feed();
    expect(seen.single.url.path, '/feed');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo', 'limit': '20'});
    expect((cards[0].yourSize, cards[0].inYourSize), ('M', true)); // we have their real size
    expect((cards[1].yourSize, cards[1].inYourSize), ('L', false)); // sold out; L is the nearest left
    expect((cards[2].yourSize, cards[2].inYourSize), (null, null)); // unknown / unsizable / older server

    await api.feed(seed: 'hm:1 2', limit: 5);
    expect(seen.last.url.queryParameters, {'user_id': 'u_demo', 'limit': '5', 'seed': 'hm:1 2'});
    expect(seen.last.headers['X-DTI-Key'], 'k');
  });

  test('search sends user + q and parses similar Products and goes_with (catalog + closet)', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'query': 'baggy jeans',
          'similar': [_card('s1'), _card('s2')],
          'goes_with': [
            {..._card('g1'), 'from_closet': false, 'reason': 'balances the volume'},
            {
              'id': 'ci_1', 'user_id': 'u_demo', 'image_url': '/static/uploads/tee.jpg', 'category': 'top',
              'color': 'white', 'label': 'White tee', 'from_closet': true, 'reason': 'already yours',
            },
          ],
        });
    final res = await api.search('baggy jeans');
    expect((seen.single.method, seen.single.url.path), ('GET', '/search'));
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo', 'q': 'baggy jeans'});
    expect(res.query, 'baggy jeans');
    expect(res.similar.map((p) => p.id), ['s1', 's2']);
    expect(res.similar.first.name, 'Piece s1');
    final catalog = res.goesWith[0];
    expect((catalog.fromCloset, catalog.product?.id, catalog.closetItem, catalog.reason), (false, 'g1', null, 'balances the volume'));
    final closet = res.goesWith[1];
    expect((closet.fromCloset, closet.product, closet.closetItem?.id, closet.reason), (true, null, 'ci_1', 'already yours'));
    expect((closet.id, closet.label, closet.imageUrl), ('ci_1', 'White tee', '/static/uploads/tee.jpg'));
    // blank query / sparse reply
    final empty = SearchResult.fromJson({'query': '', 'similar': [], 'goes_with': []});
    expect(empty.similar, isEmpty);
    expect(empty.goesWith, isEmpty);
    expect(SearchResult.fromJson({}).similar, isEmpty);
  });

  test('searchStyles sends limit and parses chips with counts and trending with trend_count', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'styles': [{'tag': 'minimalist', 'count': 312}, {'tag': 'y2k', 'count': 42}],
          'trending': [{..._card('t1'), 'trend_count': 3}, _card('t2')],
        });
    final chips = await api.searchStyles();
    expect((seen.single.method, seen.single.url.path), ('GET', '/search/styles'));
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo', 'limit': '8'});
    expect(chips.styles.map((s) => '${s.tag}:${s.count}'), ['minimalist:312', 'y2k:42']);
    expect(chips.trending.map((t) => '${t.id}:${t.trendCount}'), ['t1:3', 't2:0']);
    expect(chips.trending.first.product.name, 'Piece t1');
    await api.searchStyles(limit: 12);
    expect(seen.last.url.queryParameters['limit'], '12');
    expect(StyleChips.fromJson({}).styles, isEmpty);
  });

  test('searchPhoto uploads multipart with the real MIME and parses photo_url, tags, ranked similar', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'photo_url': '/static/uploads/q.jpg',
          'tags': [{'label': 'Baggy jeans', 'retailer': 'hm', 'box': [0.1, 0.5, 0.6, 0.9]}],
          'similar': [{..._card('s1'), 'score': 0.8, 'matched_tag': 'Baggy jeans'}],
          'goes_with': [{..._card('g1'), 'from_closet': false, 'reason': 'r'}],
        });
    final res = await api.searchPhoto([137, 80, 78, 71], mimeType: 'image/png');
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/search/photo'));
    expect(r.headers['Content-Type'], startsWith('multipart/form-data; boundary='));
    final body = utf8.decode(r.bodyBytes, allowMalformed: true);
    expect(body, contains('name="user_id"\r\n\r\nu_demo'));
    expect(body, contains('name="file"; filename="photo.png"'));
    expect(body, contains('Content-Type: image/png'));
    expect(res.photoUrl, '/static/uploads/q.jpg');
    expect(res.tags.single.box, [0.1, 0.5, 0.6, 0.9]);
    expect((res.similar.single.id, res.similar.single.matchedTag, res.similar.single.score), ('s1', 'Baggy jeans', 0.8));
    expect(res.goesWith.single.product?.id, 'g1');
  });

  test('searchPhoto 502 (AI down) surfaces the detail as ApiError', () async {
    final api = Api(client: MockClient((_) async => http.Response('{"detail": "photo search is unavailable right now"}', 502)));
    expect(api.searchPhoto([1]), throwsA(isA<ApiError>().having((e) => e.status, 'status', 502)));
  });

  test('Cart parses unavailable lines and keeps count; older servers omit them', () {
    final cart = Cart.fromJson({
      'user_id': 'u_demo', 'count': 3, 'total_usd': 40,
      'groups': [{'retailer': 'hm', 'subtotal_usd': 40, 'items': [{'product_id': 'hm:1', 'size': 'M', 'qty': 2, 'available': true}]}],
      'unavailable': [
        {'product_id': 'hm:9', 'size': 'XL', 'qty': 1, 'name': 'Old coat', 'product': _card('hm:9'), 'available': false, 'unavailable_reason': 'size sold out'},
        {'product_id': 'gone', 'size': 'S', 'qty': 1, 'name': 'Gone tee', 'product': null, 'available': false, 'unavailable_reason': 'no longer available'},
      ],
    });
    expect((cart.count, cart.totalUsd, cart.groups.single.items.single.qty), (3, 40.0, 2));
    expect(cart.unavailable.map((u) => '${u.productId}:${u.size}:${u.reason}'), ['hm:9:XL:size sold out', 'gone:S:no longer available']);
    expect(cart.unavailable[0].product?.name, 'Piece hm:9');
    expect(cart.unavailable[1].product, isNull);
    expect(Cart.fromJson({'user_id': 'u', 'groups': [], 'total_usd': 0, 'count': 0}).unavailable, isEmpty);
  });

  Map<String, dynamic> cartJson(String size, int qty) => {
        'user_id': 'u_demo', 'count': qty, 'total_usd': 20.0 * qty,
        'groups': [{'retailer': 'hm', 'subtotal_usd': 20.0 * qty, 'items': [{'product_id': 'hm:1', 'size': size, 'qty': qty}]}],
      };

  test('changeCartSize PATCHes {size, new_size} and returns the cart', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => cartJson('L', 2));
    final cart = await api.changeCartSize('hm:1', size: 'M', newSize: 'L');
    expect((seen.single.method, seen.single.url.path), ('PATCH', '/cart/u_demo/items/hm%3A1'));
    expect(jsonDecode(seen.single.body), {'size': 'M', 'new_size': 'L'});
    expect(cart.groups.single.items.single.size, 'L');
    expect(cart.count, 2);
  });

  test('StoreController.changeSize uses the atomic route when live', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => cartJson('L', 2));
    final store = StoreController(api: api, demo: false);
    await store.changeSize(const CartItem(productId: 'hm:1', size: 'M', qty: 2), 'L');
    expect(seen.map((r) => r.method), ['PATCH']);
    expect(store.cart.groups.single.items.single.size, 'L');
  });

  test('StoreController.changeSize falls back to add+remove on a server without the route', () async {
    final seen = <http.Request>[];
    final api = Api(client: MockClient((r) async {
      seen.add(r);
      if (r.method == 'PATCH') return http.Response('{"detail": "Not Found"}', 404);
      return http.Response(jsonEncode(cartJson(r.method == 'POST' ? 'M' : 'L', 2)), 200);
    }))
      ..settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
    final store = StoreController(api: api, demo: false);
    await store.changeSize(const CartItem(productId: 'hm:1', size: 'M', qty: 2), 'L');
    expect(seen.map((r) => r.method), ['PATCH', 'POST', 'DELETE']);
    expect(store.cart.groups.single.items.single.size, 'L');
  });

  test('updateUser sends preferred_stores + onboarded and parses them back', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'id': 'u_demo', 'display_name': 'Demo', 'preferred_stores': ['hm', 'uniqlo'], 'onboarded': true,
        });
    final user = await api.updateUser(preferredStores: ['hm', 'uniqlo'], onboarded: true);
    expect((seen.single.method, seen.single.url.path), ('PATCH', '/users/u_demo'));
    expect(jsonDecode(seen.single.body), {'preferred_stores': ['hm', 'uniqlo'], 'onboarded': true});
    expect(user.preferredStores, ['hm', 'uniqlo']);
    expect(user.onboarded, isTrue);
    // older user records: defaults
    final old = AppUser.fromJson({'id': 'u', 'display_name': 'U'});
    expect(old.preferredStores, isEmpty);
    expect(old.onboarded, isFalse);
  });

  test('fitCheckFeed adds author only when filtering', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => []);
    await api.fitCheckFeed();
    expect(seen.last.url.queryParameters, {'user_id': 'u_demo', 'limit': '20'});
    await api.fitCheckFeed(author: 'u_ryan', limit: 10);
    expect(seen.last.url.path, '/fitcheck/feed');
    expect(seen.last.url.queryParameters, {'user_id': 'u_demo', 'limit': '10', 'author': 'u_ryan'});
  });
}
