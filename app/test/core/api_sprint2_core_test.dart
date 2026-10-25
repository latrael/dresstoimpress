// Core (Adam) for Ryan's sprint 2: feed seedShown, shopFor, cart-line imageUrl, draft -> confirm body scan.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _user = {'id': 'u_demo', 'display_name': 'Demo', 'style_text': '', 'price_ranges': {}, 'friends': []};

Api _api(List<http.Request> seen, Object Function(http.Request) reply) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

void main() {
  test('feed sends seed_shown=true only when asked', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => []);
    await api.feed(seed: 'hm:1:black');
    expect(seen.last.url.queryParameters, {'user_id': 'u_demo', 'limit': '20', 'seed': 'hm:1:black'});
    await api.feed(seed: 'hm:1:black', seedShown: true, limit: 5);
    expect(seen.last.url.queryParameters,
        {'user_id': 'u_demo', 'limit': '5', 'seed': 'hm:1:black', 'seed_shown': 'true'});
    await api.feed(seedShown: false);
    expect(seen.last.url.queryParameters.containsKey('seed_shown'), isFalse);
  });

  test('shopFor is sent on create/update when given and parsed with a both default', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => {..._user, if (r.method == 'PATCH') 'shop_for': 'men'});
    final created = await api.createUser(displayName: 'Demo', shopFor: 'women');
    expect(jsonDecode(seen.last.body)['shop_for'], 'women');
    expect(created.shopFor, 'both'); // absent in the reply -> default
    await api.createUser(displayName: 'Demo');
    expect(jsonDecode(seen.last.body).containsKey('shop_for'), isFalse);

    final updated = await api.updateUser(shopFor: 'men');
    expect(seen.last.method, 'PATCH');
    expect(jsonDecode(seen.last.body), {'shop_for': 'men'});
    expect(updated.shopFor, 'men');
    await api.updateUser(onboarded: true);
    expect(jsonDecode(seen.last.body), {'onboarded': true}); // null shopFor is not sent
    expect(AppUser.fromJson({..._user, 'shop_for': ''}).shopFor, 'both');
  });

  test('cart lines carry the flat image_url, also for unavailable lines whose product is gone', () async {
    final api = _api([], (_) => {
          'user_id': 'u_demo', 'total_usd': 30.0, 'count': 2,
          'groups': [
            {
              'retailer': 'hm', 'subtotal_usd': 30.0,
              'items': [
                {
                  'product_id': 'hm:1:black', 'size': 'M', 'qty': 1, 'image_url': 'https://image.hm.com/a.jpg',
                  'product': {'id': 'hm:1:black', 'name': 'Tee', 'image_url': 'https://image.hm.com/a.jpg',
                    'price_usd': 30, 'retailer': 'hm', 'category': 'top'},
                  'available': true,
                }
              ],
            }
          ],
          'unavailable': [
            {'product_id': 'uniqlo:9:red', 'size': 'L', 'qty': 1, 'name': 'Old Jacket', 'product': null,
              'image_url': 'https://image.uniqlo.com/old.jpg', 'available': false,
              'unavailable_reason': 'no longer available'}
          ],
        });
    final cart = await api.cart();
    expect(cart.groups.single.items.single.imageUrl, 'https://image.hm.com/a.jpg');
    final gone = cart.unavailable.single;
    expect(gone.product, isNull);
    expect(gone.imageUrl, 'https://image.uniqlo.com/old.jpg');
    expect(gone.reason, 'no longer available');
    // older servers: no image_url on the line
    expect(CartItem.fromJson({'product_id': 'x', 'size': 'M', 'qty': 1}).imageUrl, isNull);
    expect(UnavailableItem.fromJson({'product_id': 'x', 'size': 'M', 'qty': 1, 'name': 'X', 'reason': 'r'}).imageUrl,
        isNull);
  });

  test('bodyScan(commit: false) asks for a draft and reads committed', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => {
          'body_photo_url': 'https://dti.example/static/uploads/d1.jpg',
          'body_profile': {'height_cm': 178, 'weight_kg': 72, 'waist_in': 31.5, 'inseam_in': 32, 'source': 'estimate'},
          'committed': r.url.queryParameters['commit'] != 'false',
        });
    final draft = await api.bodyScan([1, 2], heightCm: 178, weightKg: 72, commit: false);
    expect(seen.single.url.path, '/users/u_demo/body-scan');
    expect(seen.single.url.queryParameters, {'commit': 'false'});
    expect(seen.single.body, contains('name="height_cm"\r\n\r\n178.0'));
    expect(draft.committed, isFalse);
    expect(draft.profile.waistIn, 31.5);

    final saved = await api.bodyScan([1, 2], heightCm: 178);
    expect(seen.last.url.queryParameters, isEmpty); // default commit: nothing extra on the wire
    expect(saved.committed, isTrue);
    // older servers never send `committed`: treated as saved
    expect(BodyScanResult.fromJson({'body_photo_url': 'x', 'body_profile': {'height_cm': 170}}).committed, isTrue);
  });

  test('confirmBodyScan posts the draft profile with the edits applied and listed', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'body_photo_url': 'https://dti.example/static/uploads/d1.jpg',
          'body_profile': {'height_cm': 178, 'weight_kg': 72, 'waist_in': 33, 'inseam_in': 32, 'fit': 'slim',
            'source': 'manual', 'manual': ['fit', 'waist_in']},
          'committed': true,
        });
    final draft = BodyScanResult.fromJson({
      'body_photo_url': 'https://dti.example/static/uploads/d1.jpg',
      'body_profile': {'height_cm': 178, 'weight_kg': 72, 'chest_in': null, 'waist_in': 31.5, 'inseam_in': 32,
        'build': 'slim', 'source': 'estimate', 'full_body': true, 'note': 'Nice', 'scanned_at': '2026-10-24T00:00:00+00:00'},
      'committed': false,
    });
    final res = await api.confirmBodyScan(draft, waistIn: 33, fit: 'slim');
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/users/u_demo/body-scan/confirm'));
    final body = jsonDecode(r.body) as Map;
    expect(body['body_photo_url'], 'https://dti.example/static/uploads/d1.jpg');
    expect(body['edited'], ['waist_in', 'fit']);
    final profile = body['profile'] as Map;
    expect(profile['waist_in'], 33.0); // edited value replaces the draft's 31.5
    expect(profile['fit'], 'slim');
    expect(profile['inseam_in'], 32.0); // untouched scan values travel with it
    expect(profile['height_cm'], 178.0);
    expect(profile['source'], 'estimate');
    expect(profile['build'], 'slim');
    expect(profile.containsKey('chest_in'), isTrue); // nulls are kept
    expect(res.committed, isTrue);
    expect(res.profile.manual, ['fit', 'waist_in']);

    await api.confirmBodyScan(draft); // accepted as-is: no edits
    expect(jsonDecode(seen.last.body)['edited'], isEmpty);
  });
}
