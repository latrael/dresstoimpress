// Core (Adam): digitize wardrobe, body scan and body profile (PR #22) against the backend contracts.
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
