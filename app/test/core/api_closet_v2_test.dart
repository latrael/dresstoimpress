// Core (Adam): closet v2 against the backend contracts (docs/schema.md "Closet v2"): multi-photo
// piece/outfit upload, brand + catalog match + standalone display image, worn-in fits, edit, reshoot.
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

const _tee = {
  'id': 'ci_tee', 'user_id': 'u_demo', 'image_url': 'https://image.hm.com/tee.jpg', 'category': 'top',
  'color': 'black', 'pattern': 'solid', 'style_tags': ['y2k'], 'formality': 2, 'source': 'photo',
  'label': 'black baby tee', 'duplicate_of': null,
  'brand': 'H&M', 'product_id': 'hm:tee:black', 'catalog_image_url': 'https://image.hm.com/tee.jpg',
  'match_confidence': 0.9, 'display_image_url': 'https://image.hm.com/tee.jpg',
  'crop_image_url': 'https://dti.example/static/uploads/crop1.jpg',
  'worn_in': [
    {'photo_url': 'https://dti.example/static/uploads/fit1.jpg', 'at': '2026-10-24T23:10:00+00:00', 'source': 'closet'},
    {'photo_url': 'https://dti.example/static/uploads/fit2.jpg', 'at': '2026-10-24T23:40:00+00:00', 'source': 'fitcheck'},
  ],
};

const _cargos = {
  'id': 'ci_cargo', 'user_id': 'u_demo', 'image_url': 'https://dti.example/static/uploads/c-clean.png',
  'category': 'bottom', 'color': 'black', 'label': 'black cargo pants', 'brand': null, 'product_id': null,
  'display_image_url': 'https://dti.example/static/uploads/c-clean.png',
  'crop_image_url': 'https://dti.example/static/uploads/c-crop.jpg',
  'worn_in': [{'photo_url': 'https://dti.example/static/uploads/fit1.jpg', 'at': '2026-10-24T23:10:00+00:00', 'source': 'closet'}],
};

int _count(String body, String needle) => needle.allMatches(body).length;

void main() {
  test('ClosetItem parses the v2 fields and tolerates old items', () {
    final tee = ClosetItem.fromJson(Map<String, dynamic>.from(_tee));
    expect(tee.brand, 'H&M');
    expect(tee.productId, 'hm:tee:black');
    expect(tee.catalogImageUrl, 'https://image.hm.com/tee.jpg');
    expect(tee.matchConfidence, 0.9);
    expect(tee.displayImageUrl, 'https://image.hm.com/tee.jpg');
    expect(tee.shownImageUrl, tee.displayImageUrl);
    expect(tee.cropImageUrl, 'https://dti.example/static/uploads/crop1.jpg');
    expect(tee.wornIn.length, 2);
    expect(tee.wornIn.first.photoUrl, 'https://dti.example/static/uploads/fit1.jpg');
    expect(tee.wornIn.first.source, 'closet');
    expect(tee.wornIn.last.source, 'fitcheck');
    expect(tee.wornIn.last.time, DateTime.utc(2026, 10, 24, 23, 40));

    final old = ClosetItem.fromJson({
      'id': 'ci_old', 'user_id': 'u_demo', 'image_url': '/static/uploads/old.jpg', 'category': 'top', 'color': 'white',
    });
    expect(old.brand, isNull);
    expect(old.productId, isNull);
    expect(old.matchConfidence, isNull);
    expect(old.displayImageUrl, isNull);
    expect(old.shownImageUrl, '/static/uploads/old.jpg');
    expect(old.wornIn, isEmpty);
  });

  test('uploadClosetPhotos sends N files parts + kind and parses added / merged / skipped', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'added': [_cargos], 'merged': [_tee], 'skipped': 1});
    final res = await api.uploadClosetPhotos([
      [1, 2, 3],
      [4, 5],
      [6],
    ], kind: 'outfit', mimeTypes: ['image/jpeg', 'image/png', 'image/heic']);

    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/closet/upload'));
    expect(r.headers['X-DTI-Key'], 'k');
    expect(r.headers['Content-Type'], startsWith('multipart/form-data; boundary='));
    final body = latin1.decode(r.bodyBytes);
    expect(_count(body, 'name="files"'), 3);
    expect(_count(body, 'name="file"'), 0); // only the multi-file field
    expect(body, contains('name="user_id"\r\n\r\nu_demo\r\n'));
    expect(body, contains('name="kind"\r\n\r\noutfit\r\n'));
    expect(body, contains('filename="photo1.jpeg"\r\nContent-Type: image/jpeg\r\n\r\n\u0001\u0002\u0003\r\n'));
    expect(body, contains('filename="photo2.png"\r\nContent-Type: image/png\r\n\r\n\u0004\u0005\r\n'));
    expect(body, contains('filename="photo3.heic"\r\nContent-Type: image/heic\r\n\r\n\u0006\r\n'));
    expect(body, endsWith('--\r\n'));

    expect(res.added.map((i) => i.id), ['ci_cargo']);
    expect(res.merged.map((i) => i.id), ['ci_tee']);
    expect(res.skipped, 1);
    expect(res.all.map((i) => i.label), ['black cargo pants', 'black baby tee']);
    expect(res.added.single.shownImageUrl, 'https://dti.example/static/uploads/c-clean.png');
    expect(res.added.single.brand, isNull);
  });

  test('uploadClosetPhotos kind piece defaults every photo to jpeg', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'added': [_tee], 'merged': [], 'skipped': 0});
    final res = await api.uploadClosetPhotos([
      [1],
      [2],
    ], kind: 'piece');
    final body = latin1.decode(seen.single.bodyBytes);
    expect(_count(body, 'name="files"'), 2);
    expect(_count(body, 'Content-Type: image/jpeg'), 2);
    expect(body, contains('name="kind"\r\n\r\npiece\r\n'));
    expect(res.added.single.brand, 'H&M');
    expect(res.merged, isEmpty);
  });

  test('updateClosetItem PATCHes only the given fields; clearProduct sends product_id null', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {..._tee, 'label': 'stussy tee', 'brand': 'Stüssy'});
    final item = await api.updateClosetItem('ci_tee', label: 'stussy tee', brand: 'Stüssy');
    var r = seen.single;
    expect((r.method, r.url.path), ('PATCH', '/closet/u_demo/ci_tee'));
    expect(r.headers['Content-Type'], contains('application/json'));
    expect(jsonDecode(r.body), {'label': 'stussy tee', 'brand': 'Stüssy'});
    expect((item.label, item.brand), ('stussy tee', 'Stüssy'));

    seen.clear();
    await api.updateClosetItem('ci_tee', productId: 'hm:tee:black', category: 'top', color: 'black');
    expect(jsonDecode(seen.single.body), {'product_id': 'hm:tee:black', 'category': 'top', 'color': 'black'});

    seen.clear();
    final api2 = _api(seen, (_) => {
          ..._tee, 'product_id': null, 'catalog_image_url': null, 'match_confidence': null,
          'display_image_url': 'https://dti.example/static/uploads/crop1.jpg',
          'image_url': 'https://dti.example/static/uploads/crop1.jpg',
        });
    final cleared = await api2.updateClosetItem('ci_tee', clearProduct: true);
    r = seen.single;
    expect(r.body, '{"product_id":null}'); // null must reach the server (it means "unlink")
    expect(cleared.productId, isNull);
    expect(cleared.shownImageUrl, 'https://dti.example/static/uploads/crop1.jpg');
  });

  test('reshootClosetItem POSTs to /reshoot and returns the item with its new picture', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          ..._cargos, 'display_image_url': 'https://dti.example/static/uploads/c2-clean.png',
          'image_url': 'https://dti.example/static/uploads/c2-clean.png',
        });
    final item = await api.reshootClosetItem('ci_cargo');
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/closet/u_demo/ci_cargo/reshoot'));
    expect(r.headers['X-DTI-Key'], 'k');
    expect(item.displayImageUrl, 'https://dti.example/static/uploads/c2-clean.png');
    expect(item.cropImageUrl, 'https://dti.example/static/uploads/c-crop.jpg'); // the crop stays
  });

  test('server errors on closet v2 routes surface as ApiError', () async {
    final api = _api([], (_) => {'detail': 'not your closet item'}, status: 403);
    await expectLater(api.updateClosetItem('ci_x', label: 'x'),
        throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)));
    final api2 = _api([], (_) => {'detail': 'kind must be piece or outfit'}, status: 422);
    await expectLater(api2.uploadClosetPhotos([[1]], kind: 'outfit'),
        throwsA(isA<ApiError>().having((e) => e.message, 'message', 'kind must be piece or outfit')));
  });
}
