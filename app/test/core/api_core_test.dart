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

  test('our own photos saved under an old server address load from the current one', () {
    final api = _api([], (_) => {});
    const old = 'https://dead-tunnel.trycloudflare.com/static/uploads/ab12.jpg';
    expect(api.imageUrl(old), 'https://dti.example/static/uploads/ab12.jpg');
    expect(api.imageProxyUrl(old), 'https://dti.example/static/uploads/ab12.jpg');
    expect(api.imageProxyUrl('http://localhost:8000/static/tryon/t1.png'), 'https://dti.example/static/tryon/t1.png');
    // other hosts' /static paths and retailer images are left alone
    expect(api.imageUrl('https://cdn.example.com/static/css/x.png'), 'https://cdn.example.com/static/css/x.png');
    expect(api.imageUrl('https://image.hm.com/static/uploads/a.jpg?w=1'), 'https://image.hm.com/static/uploads/a.jpg?w=1');
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

  test('deleteFitCheck sends DELETE with the owner id and reads deleted', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => {'post_id': 'fc 1', 'deleted': true});
    expect(await api.deleteFitCheck('fc 1'), isTrue);
    final r = seen.single;
    expect(r.method, 'DELETE');
    expect(r.url.path, '/fitcheck/fc%201');
    expect(r.url.queryParameters, {'user_id': 'u_demo'});
    expect(r.headers['X-DTI-Key'], 'k');
  });
}
