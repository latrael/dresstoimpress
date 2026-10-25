// Core (Adam): POST /onboarding/photos — several photos in one multipart request, parsed result.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _reply = {
  'closet_added': [
    {'id': 'ci_1', 'user_id': 'u_demo', 'image_url': 'http://localhost:8000/static/uploads/a.jpg', 'category': 'top',
     'color': 'grey', 'pattern': 'solid', 'style_tags': ['streetwear'], 'formality': 2, 'label': 'grey hoodie'},
    {'id': 'ci_2', 'user_id': 'u_demo', 'image_url': 'http://localhost:8000/static/uploads/b.jpg', 'category': 'bottom',
     'color': 'light blue', 'pattern': 'solid', 'style_tags': ['streetwear', 'vintage'], 'formality': 2,
     'label': 'light wash jeans'},
  ],
  'closet_skipped_duplicates': 3,
  'body_profile': {'height_cm': 178, 'weight_kg': 72, 'chest_in': 38, 'waist_in': 31, 'hip_in': 38, 'inseam_in': 32,
                   'build': 'slim', 'source': 'ai', 'full_body': true, 'note': 'Long legs', 'manual': [],
                   'scan_photos': 2, 'confidence': 'medium'},
  'body_photo_url': 'http://localhost:8000/static/uploads/me.jpg',
  'shop_for': 'men',
  'style': {'style_text': 'streetwear and vintage; grey hoodie, light wash jeans; mostly casual',
            'style_tags': ['streetwear', 'vintage'], 'colors': ['grey', 'light blue'], 'formality': 'casual'},
  'user': {'id': 'u_demo', 'display_name': 'Demo', 'style_text': 'streetwear and vintage; grey hoodie',
           'style_tags': ['streetwear', 'vintage'], 'price_ranges': {}, 'onboarded': true, 'friends': []},
};

Api _api(List<http.Request> seen, {Object reply = _reply, int status = 200}) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply), status, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

/// Parts of a hand-built multipart body: (headers, body bytes) per part.
List<(String, List<int>)> _parts(http.Request r) {
  final boundary = RegExp(r'boundary=(.+)$').firstMatch(r.headers['Content-Type']!)!.group(1)!;
  final body = r.bodyBytes;
  final text = latin1.decode(body);
  final out = <(String, List<int>)>[];
  final marker = '--$boundary';
  var pos = text.indexOf(marker);
  while (pos >= 0) {
    final start = pos + marker.length;
    if (text.startsWith('--', start)) break; // closing boundary
    final headerEnd = text.indexOf('\r\n\r\n', start);
    final next = text.indexOf('\r\n$marker', headerEnd);
    out.add((text.substring(start + 2, headerEnd), body.sublist(headerEnd + 4, next)));
    pos = next + 2;
  }
  return out;
}

void main() {
  test('onboardFromPhotos sends every photo as a `files` part plus the form fields', () async {
    final seen = <http.Request>[];
    final api = _api(seen);
    final photos = [
      [0xFF, 0xD8, 1, 2, 3],
      [0x89, 0x50, 4, 5],
      [0xFF, 0xD8, 6],
    ];
    final res = await api.onboardFromPhotos(photos,
        heightCm: 178, weightKg: 72, styleHint: ' Y2K, tops under \$40 ', mimeTypes: ['image/jpeg', 'image/png']);

    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/onboarding/photos'));
    expect(r.headers['X-DTI-Key'], 'k');
    expect(r.headers['Content-Type'], startsWith('multipart/form-data; boundary='));

    final parts = _parts(r);
    final fields = <String, String>{};
    final files = <(String, String, List<int>)>[]; // (name, content-type, bytes)
    for (final (headers, bytes) in parts) {
      final name = RegExp(r'name="([^"]+)"').firstMatch(headers)!.group(1)!;
      if (headers.contains('filename=')) {
        final ct = RegExp(r'Content-Type: (\S+)').firstMatch(headers)!.group(1)!;
        files.add((name, ct, bytes));
      } else {
        fields[name] = utf8.decode(bytes);
      }
    }
    expect(fields, {'user_id': 'u_demo', 'height_cm': '178.0', 'weight_kg': '72.0', 'style_hint': 'Y2K, tops under \$40'});
    expect(files.length, 3);
    expect(files.map((f) => f.$1).toSet(), {'files'});
    expect(files.map((f) => f.$2).toList(), ['image/jpeg', 'image/png', 'image/jpeg']); // missing mime -> jpeg
    expect(files.map((f) => f.$3).toList(), photos);
    expect(parts.length, 7);

    expect(res.closetAdded.map((c) => c.label).toList(), ['grey hoodie', 'light wash jeans']);
    expect(res.skippedDuplicates, 3);
    expect(res.bodyProfile?.waistIn, 31);
    expect(res.bodyProfile?.fullBody, isTrue);
    expect((res.bodyProfile?.scanPhotos, res.bodyProfile?.confidence), (2, 'medium'));
    expect(res.bodyProfile?.toJson()['confidence'], 'medium');
    expect(res.bodyPhotoUrl, 'http://localhost:8000/static/uploads/me.jpg');
    expect(res.styleText, 'streetwear and vintage; grey hoodie, light wash jeans; mostly casual');
    expect(res.styleTags, ['streetwear', 'vintage']);
    expect(res.colors, ['grey', 'light blue']);
    expect(res.formality, 'casual');
    expect(res.shopFor, 'men');
    expect(res.user.onboarded, isTrue);
    expect(res.user.styleTags, ['streetwear', 'vintage']);
  });

  test('optional fields are left out and a single photo is one `files` part', () async {
    final seen = <http.Request>[];
    final api = _api(seen);
    await api.onboardFromPhotos([[1, 2, 3]], heightCm: 170, styleHint: '   ');
    final parts = _parts(seen.single);
    final names = parts.map((p) => RegExp(r'name="([^"]+)"').firstMatch(p.$1)!.group(1)!).toList();
    expect(names, ['user_id', 'height_cm', 'files']);
    expect(parts.last.$1, contains('filename="photo1.jpeg"'));
  });

  test('bodyScanMany sends 1-6 photos as `files` to /users/{id}/body-scan and parses skipped / confidence', () async {
    final seen = <http.Request>[];
    final api = _api(seen, reply: {
      'body_photo_url': 'http://localhost:8000/static/uploads/me.jpg',
      'body_profile': {'height_cm': 178, 'waist_in': 31, 'source': 'ai', 'scan_photos': 3, 'confidence': 'high'},
      'skipped': 1,
      'committed': false,
    });
    final res = await api.bodyScanMany([[1], [2], [3], [4]], heightCm: 178, commit: false);
    final r = seen.single;
    expect(r.url.path, '/users/u_demo/body-scan');
    expect(r.url.queryParameters['commit'], 'false');
    final parts = _parts(r);
    final names = parts.map((p) => RegExp(r'name="([^"]+)"').firstMatch(p.$1)!.group(1)!).toList();
    expect(names, ['height_cm', 'files', 'files', 'files', 'files']);
    expect((res.skipped, res.committed), (1, false));
    expect((res.profile.scanPhotos, res.profile.confidence, res.profile.waistIn), (3, 'high', 31));
  });

  test('a 422 from the server becomes an ApiError with its detail', () async {
    final api = _api([], reply: {'detail': 'height_cm must be between 120 and 230'}, status: 422);
    expect(api.onboardFromPhotos([[1]], heightCm: 90),
        throwsA(isA<ApiError>().having((e) => e.message, 'message', 'height_cm must be between 120 and 230')));
  });

  test('PhotoOnboardingResult tolerates a sparse reply', () {
    final res = PhotoOnboardingResult.fromJson({'user': {'id': 'u'}});
    expect(res.closetAdded, isEmpty);
    expect((res.skippedDuplicates, res.bodyProfile, res.bodyPhotoUrl), (0, null, null));
    expect((res.styleText, res.formality, res.shopFor), ('', 'unknown', 'both'));
    expect(res.styleTags, isEmpty);
    expect(res.colors, isEmpty);
    expect(res.user.id, 'u');
  });
}
