// Core (Adam): image proxy helper, search, users/onboarding and Style DNA apply against the backend contracts.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _user = {
  'id': 'u_demo', 'display_name': 'Demo', 'style_text': 'Y2K, tops under \$40',
  'price_ranges': {'top': [0, 40]}, 'body_photo_url': null, 'friends': ['u_adam'],
};

Api _api(List<http.Request> seen, Object Function(http.Request) reply) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

void main() {
  test('imageProxyUrl routes retailer images through /img, leaves the rest', () {
    final api = _api([], (_) => {});
    const hm = 'https://image.hm.com/assets/hm/x.jpg?imwidth=657';
    expect(api.imageProxyUrl(hm), 'https://dti.example/img?url=${Uri.encodeQueryComponent(hm)}');
    expect(Uri.parse(api.imageProxyUrl(hm)).queryParameters['url'], hm);
    expect(api.imageProxyUrl('/static/tryon/a.png'), 'https://dti.example/static/tryon/a.png');
    expect(api.imageProxyUrl('https://example.com/a.jpg'), 'https://example.com/a.jpg');
    expect(api.imageProxyUrl('http://image.hm.com/a.jpg'), 'http://image.hm.com/a.jpg');
    expect(api.imageUrl('https://image.hm.com/a.jpg'), 'https://image.hm.com/a.jpg'); // unchanged contract
  });

  test('searchProducts sends the query and parses a page', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'items': [
            {'id': 'hm:1:black', 'retailer': 'hm', 'name': 'Baggy Jeans', 'price_usd': 29.99, 'category': 'bottom'}
          ],
          'total': 30, 'limit': 1, 'offset': 0, 'next_offset': 1,
        });
    final page = await api.searchProducts(q: 'baggy jeans', category: 'bottom', limit: 1);
    final r = seen.single;
    expect(r.method, 'GET');
    expect(r.url.path, '/products');
    expect(r.url.queryParameters, {
      'q': 'baggy jeans', 'category': 'bottom', 'in_stock': 'true', 'sort': 'relevance', 'limit': '1', 'offset': '0',
    });
    expect(r.headers['X-DTI-Key'], 'k');
    expect(page.items.single.name, 'Baggy Jeans');
    expect((page.total, page.nextOffset), (30, 1));
  });

  test('users and onboarding hit the right routes with null fields dropped', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => r.url.path == '/onboarding'
        ? {'user': _user, 'parsed': {'styles': ['y2k'], 'budgets': {'top': [0, 40]}, 'unmatched': ''}}
        : _user);

    final created = await api.createUser(displayName: 'Demo', styleText: 'Y2K');
    expect((seen.last.method, seen.last.url.path), ('POST', '/users'));
    expect(jsonDecode(seen.last.body), {'display_name': 'Demo', 'style_text': 'Y2K', 'friends': []});
    expect(created.priceRanges['top'], [0, 40]);

    final got = await api.getUser('u_x');
    expect((seen.last.method, seen.last.url.path), ('GET', '/users/u_x'));
    expect(got.friends, ['u_adam']);

    await api.updateUser(styleText: 'grunge');
    expect((seen.last.method, seen.last.url.path), ('PATCH', '/users/u_demo'));
    expect(jsonDecode(seen.last.body), {'style_text': 'grunge'});

    final onb = await api.onboarding('Y2K, tops under \$40');
    expect((seen.last.method, seen.last.url.path), ('POST', '/onboarding'));
    expect(jsonDecode(seen.last.body), {'user_id': 'u_demo', 'text': 'Y2K, tops under \$40'});
    expect(onb.styles, ['y2k']);
    expect(onb.budgets['top'], [0, 40]);
    expect(onb.user.displayName, 'Demo');
  });

  test('applyStyle posts and parses user + profile', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'user': _user,
          'profile': {'headline': 'Y2K in clean neutrals', 'styles': [{'tag': 'y2k', 'share': 1.0}],
                      'price_ranges': {'top': [20, 40]}, 'confidence': 'medium'},
        });
    final res = await api.applyStyle();
    expect((seen.single.method, seen.single.url.path), ('POST', '/users/u_demo/style/apply'));
    expect(res.profile.headline, 'Y2K in clean neutrals');
    expect(res.profile.priceRanges['top'], [20, 40]);
    expect(res.user.id, 'u_demo');
  });

  test('applyStyle surfaces the 409 detail', () async {
    final api = Api(client: MockClient((_) async => http.Response('{"detail": "like at least 5 items first"}', 409)));
    expect(api.applyStyle(), throwsA(isA<ApiError>().having((e) => e.message, 'message', 'like at least 5 items first')));
  });

  test('ProductPage tolerates missing fields', () {
    final p = ProductPage.fromJson({});
    expect(p.items, isEmpty);
    expect((p.total, p.nextOffset), (0, null));
  });

  test('digitizeCloset uploads one photo and returns every garment', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => [
          {'id': 'ci_1', 'user_id': 'u_demo', 'image_url': '/static/uploads/a.jpg', 'category': 'bottom',
           'color': 'black', 'label': 'black cargo pants'},
          {'id': 'ci_2', 'user_id': 'u_demo', 'image_url': '/static/uploads/b.jpg', 'category': 'top',
           'color': 'white', 'label': 'white baby tee', 'duplicate_of': 'ci_0'},
        ]);
    final items = await api.digitizeCloset([1, 2, 3]);
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/closet/digitize'));
    expect(r.body, contains('name="user_id"\r\n\r\nu_demo'));
    expect(r.body, contains('Content-Type: image/jpeg'));
    expect(items.map((i) => i.label), ['black cargo pants', 'white baby tee']);
    expect(items.last.duplicateOf, 'ci_0');
  });

  test('bodyScan sends height and weight and parses the profile', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'body_photo_url': 'https://dti.example/static/uploads/me.jpg',
          'body_profile': {'height_cm': 178, 'weight_kg': 72, 'chest_in': 40, 'waist_in': 31.5, 'hip_in': null,
                           'inseam_in': 32, 'build': 'athletic', 'source': 'ai', 'full_body': true,
                           'note': 'Long legs, pick longer inseams', 'scanned_at': '2026-10-24T21:30:00+00:00'},
        });
    final res = await api.bodyScan([1, 2], heightCm: 178, weightKg: 72);
    final r = seen.single;
    expect(r.url.path, '/users/u_demo/body-scan');
    expect(r.body, contains('name="height_cm"\r\n\r\n178.0'));
    expect(r.body, contains('name="weight_kg"\r\n\r\n72.0'));
    expect(res.bodyPhotoUrl, endsWith('/me.jpg'));
    expect((res.profile.waistIn, res.profile.hipIn, res.profile.source), (31.5, null, 'ai'));
    expect(res.profile.fullBody, isTrue);

    final noWeight = _api(<http.Request>[], (_) => {'body_photo_url': 'x', 'body_profile': {'height_cm': 170}});
    expect((await noWeight.bodyScan([1], heightCm: 170)).profile.source, 'estimate');
  });

  test('updateBodyProfile sends only what is given, in cm, and parses the saved profile', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'height_cm': 175, 'waist_in': 32, 'fit': 'oversized', 'shoe_us': 10, 'source': 'manual',
          'usual_sizes': {'top': 'M'}, 'manual': ['height_cm', 'waist_in'],
        });
    final p = await api.updateBodyProfile(heightCm: 175, waistCm: 81.3, fit: 'oversized', usualSizes: {'top': 'M'});
    final r = seen.single;
    expect((r.method, r.url.path), ('PATCH', '/users/u_demo/body-profile'));
    expect(jsonDecode(r.body), {'height_cm': 175.0, 'waist_cm': 81.3, 'fit': 'oversized', 'usual_sizes': {'top': 'M'}});
    expect((p.waistIn, p.fit, p.shoeUs, p.source), (32.0, 'oversized', 10.0, 'manual'));
    expect(p.usualSizes, {'top': 'M'});
    expect(p.manual, ['height_cm', 'waist_in']);
  });

  test('AppUser carries the body scan; sizeAdvice sends the user id', () async {
    final u = AppUser.fromJson({..._user, 'body_profile': {'height_cm': 170, 'waist_in': 30, 'source': 'estimate'}});
    expect(u.bodyProfile?.waistIn, 30);
    expect(AppUser.fromJson(_user).bodyProfile, isNull);

    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'size': 'M', 'confidence': 'high', 'reason': 'x'});
    await api.sizeAdvice('hm:1:black');
    expect((jsonDecode(seen.single.body) as Map)['user_id'], 'u_demo');
  });
}
