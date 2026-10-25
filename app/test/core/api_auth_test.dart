// Google sign-in (docs/auth-google.md): POST /auth/google, the Bearer session header, /auth/me, /auth/logout.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Api _api(List<http.Request> seen, Object? Function(http.Request) reply, {String token = ''}) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = Settings(baseUrl: 'https://dti.example', apiKey: 'k', userId: 'u_nabil', sessionToken: token);
  return api;
}

const _user = {'id': 'u_ada-3f2a', 'display_name': 'Ada'};

void main() {
  test('signInWithGoogle posts the ID token (and an optional link) and parses the session', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => {'token': 'sess-1', 'user': _user, 'created': true});
    final s = await api.signInWithGoogle('google-id-token');
    expect((s.token, s.user.id, s.user.displayName, s.created), ('sess-1', 'u_ada-3f2a', 'Ada', true));
    expect(seen.single.url.path, '/auth/google');
    expect(jsonDecode(seen.single.body), {'id_token': 'google-id-token'}); // no link: field left out
    expect(seen.single.headers['X-DTI-Key'], 'k');

    await api.signInWithGoogle('t2', linkUserId: 'u_nabil');
    expect(jsonDecode(seen.last.body), {'id_token': 't2', 'link_user_id': 'u_nabil'});
  });

  test('a saved session token goes on every call as Bearer; none without one', () async {
    final seen = <http.Request>[];
    await _api(seen, (_) => {'items': [], 'total_usd': 0}, token: 'sess-9').cart();
    expect(seen.single.headers['Authorization'], 'Bearer sess-9');
    final plain = <http.Request>[];
    await _api(plain, (_) => {'items': [], 'total_usd': 0}).cart();
    expect(plain.single.headers.containsKey('Authorization'), isFalse);
  });

  test('me reads the signed-in user; logout revokes', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (r) => r.url.path == '/auth/me' ? _user : {'revoked': true}, token: 'sess-9');
    expect((await api.me()).id, 'u_ada-3f2a');
    await api.logout();
    expect(seen.map((r) => '${r.method} ${r.url.path}'), ['GET /auth/me', 'POST /auth/logout']);
    expect(seen.every((r) => r.headers['Authorization'] == 'Bearer sess-9'), isTrue);
  });

  test('copyWith keeps or clears the session token', () {
    const s = Settings(sessionToken: 'a');
    expect(s.copyWith(userId: 'u_x').sessionToken, 'a');
    expect(s.copyWith(sessionToken: '').sessionToken, '');
  });
}
