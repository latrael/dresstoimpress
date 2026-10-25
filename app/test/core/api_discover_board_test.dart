// Discover board: GET /discover/board (pins + products + Inspo posts) and GET /discover/pins/{id}/similar.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
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
  api.settings = const Settings(baseUrl: 'https://dti.example', apiKey: 'k', userId: 'u_w');
  return api;
}

const _pin = {
  'id': 'pin:1', 'image_url': 'https://i.pinimg.com/736x/a.jpg', 'w': 736, 'h': 981, 'title': 'y2k look',
  'pin_url': 'https://www.pinterest.com/pin/1/', 'dominant_color': '#79635d', 'style': 'y2k',
  'tagged': [{'label': 'baggy jeans', 'category': 'bottom'}],
};

void main() {
  test('board parses pins, products and posts; skips kinds it does not know', () {
    final b = DiscoverBoard.fromJson({
      'style': 'y2k',
      'styles': ['y2k'],
      'items': [
        {'kind': 'pin', 'pin': _pin},
        {'kind': 'product', 'product': {'id': 'p1', 'name': 'Tee', 'category': 'top', 'image_url': 'https://x/p.jpg'}},
        {'kind': 'post', 'post': {'id': 'fc_1', 'user_id': 'u_x', 'photo_url': 'https://x/f.jpg'}},
        {'kind': 'video', 'video': {}},
      ],
      'next_offset': 24,
    });
    expect(b.items.map((i) => '${i.kind}:${i.id}'), ['pin:pin:1', 'product:p1', 'post:fc_1']);
    final pin = b.items.first.pin!;
    expect((pin.w, pin.h, pin.style, pin.dominantColor), (736, 981, 'y2k', '#79635d'));
    expect(pin.aspect, closeTo(.75, .01));
    expect(pin.tagged.single.label, 'baggy jeans');
    expect((b.style, b.nextOffset), ('y2k', 24));
    expect(b.styles, ['y2k']);
  });

  test('discoverBoard sends style + paging; pinSimilar hits the pin route', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => r.url.path == '/discover/board' ? {'items': [], 'next_offset': null} : []);
    await api.discoverBoard(style: 'grunge', limit: 24, offset: 48);
    expect(seen.last.url.queryParameters, {'user_id': 'u_w', 'style': 'grunge', 'limit': '24', 'offset': '48'});
    await api.discoverBoard();
    expect(seen.last.url.queryParameters.containsKey('style'), isFalse); // For you
    await api.pinSimilar('pin:1');
    expect(seen.last.url.path, '/discover/pins/pin%3A1/similar');
    expect(seen.last.url.queryParameters['user_id'], 'u_w');
  });
}
