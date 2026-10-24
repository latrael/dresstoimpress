// Core (Adam): Inspo tag pin boxes, Discover vibe search and body photo delete against the backend contracts.
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
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

void main() {
  test('FitTag keeps a valid pin box, drops a bad one, and round-trips it', () {
    final t = FitTag.fromJson({'label': 'baggy jeans', 'box': [0.25, 0.5, 0.75, 0.95]});
    expect(t.box, [0.25, 0.5, 0.75, 0.95]);
    expect(t.toJson()['box'], [0.25, 0.5, 0.75, 0.95]);
    expect(FitTag.fromJson({...t.toJson(), 'label': 'light jeans'}).box, t.box); // tag edit keeps it
    for (final bad in [null, 'nope', [0.1, 0.2, 0.3], [0.5, 0.2, 0.3, 0.4], [0, 0, 2, 1], ['a', 0, 1, 1]]) {
      expect(FitTag.fromJson({'label': 'x', 'box': bad}).box, isNull, reason: '$bad');
    }
    expect(FitTag.fromJson({'label': 'x'}).toJson().containsKey('box'), isFalse);
  });

  test('vibe posts the sentence and parses the filters', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {
          'styles': ['classic'], 'categories': ['top'], 'colors': ['black'],
          'keywords': ['satin shirt'], 'source': 'ai',
        });
    final v = await api.vibe('fit for a rooftop party');
    final r = seen.single;
    expect((r.method, r.url.path), ('POST', '/ai/vibe'));
    expect(jsonDecode(r.body), {'q': 'fit for a rooftop party'});
    expect(v.styles, ['classic']);
    expect(v.categories, ['top']);
    expect(v.colors, ['black']);
    expect(v.keywords, ['satin shirt']);
    expect(v.source, 'ai');
    expect(v.isEmpty, isFalse);
    expect(VibeQuery.fromJson({}).isEmpty, isTrue);
  });

  test('deleteBodyPhoto calls DELETE on the current user', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'deleted': true});
    expect(await api.deleteBodyPhoto(), isTrue);
    expect((seen.single.method, seen.single.url.path), ('DELETE', '/users/u_demo/body-photo'));
  });
}
