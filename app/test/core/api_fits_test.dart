// Core (Adam): AI Fit Creator — createFits / fit / fitTryOn / addFitToCart against the backend contract.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
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

const _closetTee = {
  'id': 'ci_1', 'user_id': 'u_demo', 'image_url': 'https://dti.example/static/uploads/t.jpg', 'category': 'top',
  'color': 'white', 'label': 'white tee', 'style_tags': ['streetwear'], 'formality': 2, 'pattern': 'solid',
};
const _jeans = {
  'id': 'hm:1', 'retailer': 'hm', 'name': 'Tapered Jeans', 'category': 'bottom', 'price_usd': 29.99,
  'image_url': 'https://image.hm.com/j.jpg', 'sizes': [{'name': '30', 'in_stock': true}], 'in_stock': true,
};
const _shoes = {
  'id': 'hm:2', 'retailer': 'hm', 'name': 'Court Sneaker', 'category': 'shoes', 'price_usd': 40.0,
  'image_url': 'https://image.hm.com/s.jpg', 'sizes': [{'name': '10', 'in_stock': true}], 'in_stock': true,
};
const _fit = {
  'id': 'fit_abc123', 'name': 'Rooftop Clean', 'occasion': 'rooftop party',
  'reason': 'Slim build, 30.5 in waist: tapered denim keeps the line clean under your white tee.',
  'pieces': [
    {'slot': 'top', 'source': 'closet', 'closet_item': _closetTee, 'product': null, 'your_size': null, 'in_your_size': null},
    {'slot': 'bottom', 'source': 'catalog', 'closet_item': null, 'product': _jeans, 'your_size': '30', 'in_your_size': true},
    {'slot': 'shoes', 'source': 'catalog', 'closet_item': null, 'product': _shoes, 'your_size': '10', 'in_your_size': false},
  ],
  'new_total_usd': 69.99, 'closet_count': 1, 'try_on': null,
};

void main() {
  _closetOnlyTests();
  test('createFits posts the request, defaults tryon off and parses fits', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'fits': [_fit], 'source': 'ai'});
    final fits = await api.createFits(occasion: 'rooftop party', mustInclude: ['hm:1'], budgetUsd: 100);
    final r = seen.single;
    expect(r.method, 'POST');
    expect(r.url.path, '/fits/create');
    expect(r.url.queryParameters, isEmpty);
    expect(r.headers['X-DTI-Key'], 'k');
    expect(jsonDecode(r.body), {
      'user_id': 'u_demo', 'count': 3, 'occasion': 'rooftop party', 'must_include': ['hm:1'], 'budget_usd': 100,
    });
    final f = fits.single;
    expect(f.id, 'fit_abc123');
    expect(f.name, 'Rooftop Clean');
    expect(f.occasion, 'rooftop party');
    expect(f.reason, contains('30.5 in waist'));
    expect(f.newTotalUsd, 69.99);
    expect(f.closetCount, 1);
    expect(f.tryOnUrl, isNull);
    expect(f.tryOnMode, isNull);
    expect(f.pieces.map((p) => p.slot), ['top', 'bottom', 'shoes']);
    final top = f.pieces[0];
    expect(top.fromCloset, isTrue);
    expect(top.closetItem?.label, 'white tee');
    expect(top.product, isNull);
    expect(top.yourSize, isNull);
    expect(top.imageUrl, 'https://dti.example/static/uploads/t.jpg');
    final bottom = f.pieces[1];
    expect(bottom.fromCloset, isFalse);
    expect(bottom.product?.name, 'Tapered Jeans');
    expect(bottom.closetItem, isNull);
    expect(bottom.yourSize, '30');
    expect(bottom.inYourSize, isTrue);
    expect(f.pieces[2].inYourSize, isFalse);
    expect(f.newPieces.length, 2);
  });

  test('createFits with tryOn sends ?tryon=true, count and reads the try-on', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'fits': [
            {..._fit, 'try_on': {'image_url': 'https://dti.example/static/tryon/x.png', 'mode': 'ai'}}
          ],
          'source': 'rules',
        });
    final fits = await api.createFits(count: 1, tryOn: true);
    expect(seen.single.url.queryParameters, {'tryon': 'true'});
    expect(jsonDecode(seen.single.body), {'user_id': 'u_demo', 'count': 1}); // nulls are dropped
    expect(fits.single.tryOnUrl, 'https://dti.example/static/tryon/x.png');
    expect(fits.single.tryOnMode, 'ai');
  });

  test('fit fetches one fit by id for the current user', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _fit);
    final f = await api.fit('fit_abc123');
    expect(seen.single.method, 'GET');
    expect(seen.single.url.path, '/fits/fit_abc123');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo'});
    expect(f.pieces.length, 3);
  });

  test('fitTryOn posts and returns a TryOnResponse-like {imageUrl, mode}', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'image_url': 'https://dti.example/static/tryon/x.png', 'mode': 'ai'});
    final t = await api.fitTryOn('fit_abc123');
    expect(seen.single.method, 'POST');
    expect(seen.single.url.path, '/fits/fit_abc123/try-on');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo'});
    expect(t.imageUrl, 'https://dti.example/static/tryon/x.png');
    expect(t.mode, 'ai');
    expect(t.cached, isFalse);
    expect(t.sourcePhotoUrl, isNull); // older server: no source photo
  });

  test('try-on carries source_photo_url (the user photo it was edited from)', () async {
    final api = _api([], (_) => {
      'image_url': 'https://dti.example/static/tryon/x.png', 'cached': true, 'mode': 'ai',
      'source_photo_url': 'https://dti.example/static/uploads/fit1.jpg',
    });
    final t = await api.tryOn(['hm:1']);
    expect(t.sourcePhotoUrl, 'https://dti.example/static/uploads/fit1.jpg');
    expect(t.cached, isTrue);

    final fit = OutfitFit.fromJson({..._fit, 'try_on': {
      'image_url': 'https://dti.example/static/tryon/y.png', 'mode': 'ai',
      'source_photo_url': 'https://dti.example/static/uploads/fit2.jpg',
    }});
    expect(fit.tryOnUrl, 'https://dti.example/static/tryon/y.png');
    expect(fit.tryOnSourcePhotoUrl, 'https://dti.example/static/uploads/fit2.jpg');
    expect(OutfitFit.fromJson(_fit).tryOnSourcePhotoUrl, isNull);
  });

  test('addFitToCart posts and parses the cart', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'user_id': 'u_demo',
          'groups': [
            {
              'retailer': 'hm',
              'subtotal_usd': 69.99,
              'items': [
                {'product_id': 'hm:1', 'size': '30', 'qty': 1, 'product': _jeans, 'available': true},
                {'product_id': 'hm:2', 'size': '10', 'qty': 1, 'product': _shoes, 'available': true},
              ],
            }
          ],
          'total_usd': 69.99, 'count': 2, 'unavailable': [],
        });
    final cart = await api.addFitToCart('fit_abc123');
    expect(seen.single.method, 'POST');
    expect(seen.single.url.path, '/fits/fit_abc123/cart');
    expect(seen.single.url.queryParameters, {'user_id': 'u_demo'});
    expect(cart.groups.single.items.map((i) => '${i.productId}/${i.size}'), ['hm:1/30', 'hm:2/10']);
    expect(cart.totalUsd, 69.99);
  });

  test('expired fit surfaces as ApiError 404', () async {
    final api = _api([], (_) => {'detail': 'unknown or expired fit'}, status: 404);
    await expectLater(api.fit('fit_old'), throwsA(isA<ApiError>().having((e) => e.status, 'status', 404)));
  });
}

void _closetOnlyTests() {
  test('OutfitFit parses `missing` and tolerates its absence (closet-only fits)', () {
    final f = OutfitFit.fromJson({
      'id': 'fit_1', 'name': 'white top fit', 'reason': 'r', 'pieces': [], 'new_total_usd': 0,
      'closet_count': 2, 'try_on': null, 'missing': ['shoes'],
    });
    expect(f.missing, ['shoes']);
    expect(f.newPieces, isEmpty);
    final old = OutfitFit.fromJson({'id': 'fit_2', 'name': 'n', 'reason': 'r', 'pieces': []});
    expect(old.missing, isEmpty);
  });
}
