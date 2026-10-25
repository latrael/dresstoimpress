import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/social/social_feed.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, Object?> post(String id, String user) => {
      'id': id,
      'user_id': user,
      'user_name': user,
      'photo_url': '/static/uploads/$id.jpg',
      'caption': 'fit $id',
      'tagged': [],
      'created_at': '2026-10-25T0$id:00:00Z',
      'likes': [],
      'comments': [],
    };

Api fakeApi({required List<Map<String, Object?>> friends}) {
  final api = Api(client: MockClient((r) async {
    final p = r.url.path;
    if (p == '/users/u_adam/friends') return http.Response(jsonEncode(friends), 200);
    if (p == '/users/u_adam/code') {
      return http.Response(jsonEncode({'id': 'u_adam', 'handle': 'adam', 'friend_code': 'NCH-7K2P', 'friends_count': friends.length}), 200);
    }
    if (p == '/fitcheck/feed') {
      return http.Response(jsonEncode([post('1', 'u_nabil'), post('2', 'u_ryan'), post('3', 'u_adam')]), 200);
    }
    return http.Response('{"detail":"nope ${r.url.path}"}', 404);
  }));
  api.settings = const Settings(userId: 'u_adam', baseUrl: 'http://x', apiKey: 'k');
  return api;
}

Future<void> mount(WidgetTester t, Api api) async {
  t.view.physicalSize = const Size(430, 900);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
      home: Scaffold(body: SocialFeed(store: StoreController(api: api, demo: false), onShop: (_) {}))));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('Friends scope is the default with a friend and shows only friends + mine', (t) async {
    await mount(t, fakeApi(friends: [
      {'id': 'u_nabil', 'handle': 'nabil', 'display_name': 'Nabil'}
    ]));
    expect(find.text('Friends'), findsOneWidget);
    expect(find.text('Everyone'), findsOneWidget);
    expect(find.byKey(const ValueKey('1')), findsOneWidget); // Nabil, a friend
    expect(find.byKey(const ValueKey('3')), findsOneWidget); // mine
    expect(find.byKey(const ValueKey('2')), findsNothing); // Ryan, not a friend

    await t.tap(find.text('Everyone'));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('2')), findsOneWidget);
  });

  testWidgets('Everyone is the default without friends', (t) async {
    await mount(t, fakeApi(friends: const []));
    expect(find.byKey(const ValueKey('1')), findsOneWidget);
    expect(find.byKey(const ValueKey('2')), findsOneWidget);
    await t.tap(find.text('Friends'));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('3')), findsOneWidget);
    expect(find.byKey(const ValueKey('1')), findsNothing);
  });
}
