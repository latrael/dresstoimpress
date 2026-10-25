// Core (Adam): sprint-3 §1 closet contracts (docs/schema.md "Closet, sprint 3"): outfits + pieces
// (GET/DELETE /closet/{user}/outfits), outfit_id and clean-shot source fields on pieces, worn_in boxes,
// and the upload result's `outfits`.
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

const _pants = {
  'id': 'ci_pants', 'user_id': 'u_demo', 'image_url': 'https://dti.example/static/uploads/p-clean.png',
  'category': 'bottom', 'color': 'black', 'label': 'black cargo pants', 'brand': null, 'product_id': null,
  'display_image_url': 'https://dti.example/static/uploads/p-clean.png',
  'crop_image_url': 'https://dti.example/static/uploads/p-crop.jpg',
  'worn_in': [
    {'photo_url': 'https://dti.example/static/uploads/fit1.jpg', 'at': '2026-10-24T23:10:00+00:00', 'source': 'closet',
      'box': [0.0, 0.5, 0.5, 1.0]},
    {'photo_url': 'https://dti.example/static/uploads/fit2.jpg', 'at': '2026-10-25T01:00:00+00:00', 'source': 'fitcheck'},
  ],
  'outfit_id': 'of_1',
  'clean_source_photo_url': 'https://dti.example/static/uploads/fit1.jpg',
  'clean_source_box': [0.0, 0.5, 0.5, 1.0],
};

const _tee = {
  'id': 'ci_tee', 'user_id': 'u_demo', 'image_url': 'https://dti.example/static/uploads/t-crop.jpg',
  'category': 'top', 'color': 'black', 'label': 'black baby tee', 'brand': 'H&M', 'product_id': 'hm:tee:black',
  'catalog_image_url': 'https://image.hm.com/tee.jpg', 'match_confidence': 0.9,
  'display_image_url': 'https://dti.example/static/uploads/t-crop.jpg',
  'crop_image_url': 'https://dti.example/static/uploads/t-crop.jpg',
  'worn_in': [{'photo_url': 'https://dti.example/static/uploads/fit1.jpg', 'at': '2026-10-24T23:10:00+00:00', 'source': 'closet',
    'box': [0.0, 0.0, 0.5, 0.5]}],
  'outfit_id': 'of_1',
};

const _outfit1 = {
  'id': 'of_1', 'user_id': 'u_demo', 'photo_url': 'https://dti.example/static/uploads/fit1.jpg',
  'created_at': '2026-10-24T23:10:00+00:00', 'piece_ids': ['ci_pants', 'ci_tee'], 'source': 'closet',
  'pieces': [_pants, _tee],
};

const _outfit2 = {
  'id': 'of_2', 'user_id': 'u_demo', 'photo_url': 'https://dti.example/static/uploads/fit2.jpg',
  'created_at': '2026-10-25T01:00:00+00:00', 'piece_ids': ['ci_pants', 'ci_gone'], 'source': 'fitcheck',
  'pieces': [_pants],
};

void main() {
  test('ClosetItem parses outfit_id, clean-shot source and worn_in boxes; old items read as null', () {
    final pants = ClosetItem.fromJson(Map<String, dynamic>.from(_pants));
    expect(pants.outfitId, 'of_1');
    expect(pants.cleanSourcePhotoUrl, 'https://dti.example/static/uploads/fit1.jpg');
    expect(pants.cleanSourceBox, [0.0, 0.5, 0.5, 1.0]);
    expect(pants.wornIn.first.box, [0.0, 0.5, 0.5, 1.0]);
    expect(pants.wornIn.last.box, isNull); // an entry without a box
    final tee = ClosetItem.fromJson(Map<String, dynamic>.from(_tee));
    // a matched piece still shows the user's own picture, never the catalog photo (sprint-3 §1.2)
    expect(tee.productId, 'hm:tee:black');
    expect(tee.shownImageUrl, tee.cropImageUrl);
    expect(tee.shownImageUrl, isNot(tee.catalogImageUrl));
    expect(tee.cleanSourceBox, isNull);
    final old = ClosetItem.fromJson({'id': 'ci_old', 'user_id': 'u_demo', 'image_url': 'https://x/o.jpg', 'category': 'top', 'color': 'red'});
    expect(old.outfitId, isNull);
    expect(old.cleanSourcePhotoUrl, isNull);
    expect(old.wornIn, isEmpty);
  });

  test('ClosetOutfit parses with embedded pieces and tolerates a minimal record', () {
    final o = ClosetOutfit.fromJson(Map<String, dynamic>.from(_outfit1));
    expect(o.id, 'of_1');
    expect(o.photoUrl, 'https://dti.example/static/uploads/fit1.jpg');
    expect(o.source, 'closet');
    expect(o.time, DateTime.utc(2026, 10, 24, 23, 10));
    expect(o.pieceIds, ['ci_pants', 'ci_tee']);
    expect(o.pieces.map((p) => p.id), ['ci_pants', 'ci_tee']);
    expect(o.pieces.first.outfitId, 'of_1');
    final bare = ClosetOutfit.fromJson({'id': 'of_x', 'photo_url': 'https://x/f.jpg'});
    expect(bare.pieces, isEmpty);
    expect(bare.pieceIds, isEmpty);
    expect(bare.time, isNull);
    expect(bare.source, isNull);
  });

  test('closetOutfits GETs /closet/{user}/outfits and keeps the server order (newest first)', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => [_outfit2, _outfit1]);
    final outfits = await api.closetOutfits();
    expect(seen.single.method, 'GET');
    expect(seen.single.url.toString(), 'https://dti.example/closet/u_demo/outfits');
    expect(seen.single.headers['X-DTI-Key'], 'k');
    expect(outfits.map((o) => o.id), ['of_2', 'of_1']);
    expect(outfits.first.source, 'fitcheck');
    // a piece that was deleted is still in piece_ids but not in pieces
    expect(outfits.first.pieceIds, ['ci_pants', 'ci_gone']);
    expect(outfits.first.pieces.map((p) => p.id), ['ci_pants']);
  });

  test('deleteClosetOutfit DELETEs /closet/{user}/outfits/{id} and returns the id', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'deleted': 'of_1'});
    final r = await api.deleteClosetOutfit('of_1');
    expect(seen.single.method, 'DELETE');
    expect(seen.single.url.toString(), 'https://dti.example/closet/u_demo/outfits/of_1');
    expect(r.deleted, 'of_1');
  });

  test('deleteClosetOutfit surfaces a 404 as an ApiError', () async {
    final api = _api([], (_) => {'detail': 'unknown outfit'}, status: 404);
    expect(() => api.deleteClosetOutfit('of_missing'), throwsA(isA<ApiError>()));
  });

  test('uploadClosetPhotos(kind: outfit) parses the outfits made by the upload', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'added': [_pants, _tee], 'merged': [], 'skipped': 0, 'outfits': [_outfit1]});
    final r = await api.uploadClosetPhotos([
      [1, 2, 3]
    ], kind: 'outfit');
    expect(seen.single.url.path, '/closet/upload');
    expect(r.added.length, 2);
    expect(r.outfits.single.id, 'of_1');
    expect(r.outfits.single.pieceIds, ['ci_pants', 'ci_tee']);
    expect(r.added.every((p) => p.outfitId == 'of_1'), isTrue);
    // an older server without `outfits` still parses
    final legacy = ClosetUploadResult.fromJson({'added': [], 'merged': [], 'skipped': 1});
    expect(legacy.outfits, isEmpty);
    expect(legacy.skipped, 1);
  });
}
