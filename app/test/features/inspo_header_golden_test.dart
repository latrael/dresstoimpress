// Visual check of the Inspo header row (scope toggle · add friends · OOTD +) in both themes.
// Run with `flutter test --update-goldens test/features/inspo_header_golden_test.dart` to refresh the PNGs
// in test/goldens/; they are documentation, not a strict regression gate (fonts differ per machine).
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/shared/niche_theme.dart';
import 'package:dress_to_impress/features/social/social_feed.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';

Api fakeApi() {
  final api = Api(client: MockClient((r) async {
    if (r.url.path == '/fitcheck/feed') return http.Response('[]', 200);
    if (r.url.path == '/users/u_adam/friends') return http.Response('[]', 200);
    return http.Response('{"detail":"nope"}', 404);
  }));
  api.settings = const Settings(userId: 'u_adam', baseUrl: 'http://x', apiKey: 'k');
  return api;
}

void main() {
  for (final dark in [false, true]) {
    testWidgets('inspo header ${dark ? 'dark' : 'light'}', (t) async {
      t.view.physicalSize = const Size(1290, 360);
      t.view.devicePixelRatio = 3;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await t.pumpWidget(MaterialApp(
          theme: Niche.theme,
          darkTheme: Niche.darkTheme,
          themeMode: dark ? ThemeMode.dark : ThemeMode.light,
          home: Scaffold(
              body: SocialFeed(
                  store: StoreController(api: fakeApi(), demo: false),
                  onShop: (_) {}))));
      await t.pumpAndSettle();
      expect(find.byTooltip('Post your OOTD'), findsOneWidget);
      expect(find.byTooltip('Add friends'), findsOneWidget);
      expect(find.byTooltip('Refresh fits'), findsNothing);
      expect(find.text('Post a fit'), findsNothing);
      await expectLater(find.byType(SocialFeed).first,
          matchesGoldenFile('../goldens/inspo_header_${dark ? 'dark' : 'light'}.png'));
    });
  }
}
