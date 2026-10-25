// Core (Adam): sprint 4 §10 feed-card fields, prefetchTryOns / tryOnStatus, and the reels mocks.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/mocks.dart';
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

void main() {
  test('feed card parses hero, closet picks and tryon; old cards still parse', () {
    final c = RankedProduct.fromJson(mockReelsJson.first);
    expect(c.heroImageUrl, contains('unsplash'));
    expect(c.closetPicks.map((p) => p.category), ['top', 'shoes', 'outerwear', 'accessory']);
    expect(c.tryOn!.isReady, isTrue);
    expect(c.tryOn!.mode, 'ai');
    final old = RankedProduct.fromJson({'id': 'x', 'name': 'n', 'category': 'top', 'image_url': 'u'});
    expect(old.heroImageUrl, isNull);
    expect(old.closetPicks, isEmpty);
    expect(old.tryOn, isNull);
    expect(TryOnState.fromJson({'status': 'weird'}).status, 'none');
  });

  test('mocks cover every slide-2 state', () {
    expect(mockReelsFeed().map((c) => c.tryOn!.status), ['ready', 'pending', 'needs_photo', 'unavailable']);
  });

  test('prefetchTryOns posts up to 5 ids; tryOnStatus polls', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => {
          'a': {'status': 'pending'},
          'b': {'status': 'ready', 'image_url': 'https://x/b.png', 'mode': 'ai'},
        });
    final m = await api.prefetchTryOns(['a', 'b', 'c', 'd', 'e', 'f']);
    expect(seen.last.method, 'POST');
    expect(seen.last.url.path, '/feed/u_demo/tryons');
    expect(jsonDecode(seen.last.body)['product_ids'], hasLength(5));
    expect(m['a']!.isPending, isTrue);
    expect(m['b']!.imageUrl, 'https://x/b.png');
    await api.tryOnStatus(['a', 'b']);
    expect(seen.last.method, 'GET');
    expect(seen.last.url.queryParameters['ids'], 'a,b');
  });
}
