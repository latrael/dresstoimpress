import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/shared/pick_photo.dart';
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

// 1x1 transparent PNG so Image.memory renders in the post sheet.
final kTransparentImage = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==');
final seenScopes = <String?>[];
final postedFields = <String>[];

Api fakeApi({required List<Map<String, Object?>> friends}) {
  final api = Api(client: MockClient((r) async {
    final p = r.url.path;
    if (p == '/users/u_adam/friends') return http.Response(jsonEncode(friends), 200);
    if (p == '/users/u_adam/code') {
      return http.Response(jsonEncode({'id': 'u_adam', 'handle': 'adam', 'friend_code': 'NCH-7K2P', 'friends_count': friends.length}), 200);
    }
    if (p == '/fitcheck/feed') {
      seenScopes.add(r.url.queryParameters['scope']);
      final all = [post('1', 'u_nabil'), post('2', 'u_ryan'), post('3', 'u_adam')];
      if (r.url.queryParameters['scope'] == 'friends') {
        final circle = {'u_adam', ...friends.map((f) => f['id'] as String)};
        return http.Response(jsonEncode([for (final x in all) if (circle.contains(x['user_id'])) x]), 200);
      }
      return http.Response(jsonEncode(all), 200);
    }
    if (p == '/fitcheck' && r.method == 'POST') {
      postedFields.add(latin1.decode(r.bodyBytes));
      return http.Response(jsonEncode({...post('9', 'u_adam'), 'visibility': 'friends'}), 200);
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
  setUp(() {
    seenScopes.clear();
    postedFields.clear();
  });

  testWidgets('Everyone is the default even with friends; Friends scope asks the server', (t) async {
    await mount(t, fakeApi(friends: [
      {'id': 'u_nabil', 'handle': 'nabil', 'display_name': 'Nabil'}
    ]));
    expect(find.text('Friends'), findsOneWidget);
    expect(find.text('Everyone'), findsOneWidget);
    expect(seenScopes, [null]); // everyone: no scope param
    expect(find.byKey(const ValueKey('2')), findsOneWidget); // Ryan, not a friend, still shown

    await t.tap(find.text('Friends'));
    await t.pumpAndSettle();
    expect(seenScopes.last, 'friends');
    expect(find.byKey(const ValueKey('1')), findsOneWidget); // Nabil, a friend
    expect(find.byKey(const ValueKey('3')), findsOneWidget); // mine
    expect(find.byKey(const ValueKey('2')), findsNothing);
  });

  testWidgets('Friends scope without friends shows the Add friends empty state', (t) async {
    await mount(t, fakeApi(friends: const []));
    expect(find.byKey(const ValueKey('1')), findsOneWidget);
    await t.tap(find.text('Friends'));
    await t.pumpAndSettle();
    expect(find.text('No friends yet'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Add friends'), findsOneWidget);
    expect(find.byKey(const ValueKey('1')), findsNothing);
    expect(find.byTooltip('Add friends'), findsOneWidget); // the icon next to the toggle
  });

  testWidgets('Post sheet sends the chosen visibility (Everyone by default)', (t) async {
    final api = fakeApi(friends: const []);
    await t.pumpWidget(MaterialApp(
        home: CreateFitCheckScreen(
            api: api,
            picker: () async => PickedPhoto(kTransparentImage, 'image/jpeg'))));
    await t.pumpAndSettle();
    await t.tap(find.text('Choose outfit photo'));
    await t.pumpAndSettle();
    await t.drag(find.byType(ListView), const Offset(0, -600));
    await t.pumpAndSettle();
    expect(find.text('Everyone'), findsOneWidget);
    expect(find.text('Friends'), findsOneWidget);
    await t.tap(find.text('Friends'));
    await t.pumpAndSettle();
    final btn = t.widget<FilledButton>(find.widgetWithText(FilledButton, 'Post to Inspo'));
    expect(btn.onPressed, isNotNull, reason: 'photo chosen, so Post is enabled');
    await t.tap(find.text('Post to Inspo'));
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    expect(postedFields, hasLength(1));
    expect(postedFields.single, contains('visibility'));
    expect(postedFields.single, contains('friends'));
  });
}
