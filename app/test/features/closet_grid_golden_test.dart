// Visual check of the Closet grids (pieces 1:1, outfits 3:4, equal tiles, equal gutters) in both themes.
// Run with `flutter test --update-goldens test/features/closet_grid_golden_test.dart` to refresh the PNGs
// in test/goldens/; they are documentation, not a strict regression gate (fonts differ per machine).
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/features/closet/closet_screen.dart';
import 'package:dress_to_impress/features/shared/niche_theme.dart';

http.Response reply(Object v) => http.Response(jsonEncode(v), 200);

Map<String, dynamic> piece(String id, String label, String cat, String brand) => {
      'id': id,
      'user_id': 'u_demo',
      'label': label,
      'category': cat,
      'color': 'black',
      'brand': brand,
      'image_url': '',
      'worn_in': [],
    };

void main() {
  final pieces = [
    piece('a', 'Camel wool overcoat', 'outerwear', 'Carhartt'),
    piece('b', 'White wired earbuds', 'accessory', ''),
    piece('c', 'Black leather loafers', 'shoes', ''),
    piece('d', 'Light blue wide jeans with a very long label', 'bottom', 'Levi\'s'),
    piece('e', 'Cream graphic t-shirt', 'top', ''),
  ];
  final outfits = [
    {
      'id': 'of_1',
      'user_id': 'u_demo',
      'photo_url': '/static/uploads/outfit.jpg',
      'created_at': '2026-10-25T00:00:00Z',
      'piece_ids': ['a', 'c'],
      'pieces': [pieces[0], pieces[2]],
      'name': 'Camel overcoat & loafers',
      'posted': true,
    },
    {
      'id': 'of_2',
      'user_id': 'u_demo',
      'photo_url': '/static/uploads/outfit.jpg',
      'created_at': '2026-10-24T00:00:00Z',
      'piece_ids': ['e', 'd'],
      'pieces': [pieces[4], pieces[3]],
      'name': 'Date night',
    },
    {
      'id': 'of_3',
      'user_id': 'u_demo',
      'photo_url': '/static/uploads/outfit.jpg',
      'created_at': '2026-10-23T00:00:00Z',
      'piece_ids': ['b'],
      'pieces': [pieces[1]],
      'name': 'White earbuds',
    },
  ];
  Api api() => Api(
      client: MockClient((r) async =>
          r.url.path.endsWith('/outfits') ? reply(outfits) : reply(pieces)));

  for (final dark in [false, true]) {
    for (final view in ['pieces', 'outfits']) {
      testWidgets('closet $view grid ${dark ? 'dark' : 'light'}', (t) async {
        t.view.physicalSize = const Size(402, 874);
        t.view.devicePixelRatio = 1;
        addTearDown(t.view.resetPhysicalSize);
        addTearDown(t.view.resetDevicePixelRatio);
        await t.pumpWidget(MaterialApp(
            theme: Niche.theme,
            darkTheme: Niche.darkTheme,
            themeMode: dark ? ThemeMode.dark : ThemeMode.light,
            home: ClosetScreen(api: api())));
        await t.pumpAndSettle();
        if (view == 'outfits') {
          await t.tap(find.text('Outfits'));
          await t.pumpAndSettle();
        }
        await expectLater(find.byType(ClosetScreen),
            matchesGoldenFile('../goldens/closet_${view}_${dark ? 'dark' : 'light'}.png'));
      });
    }
  }
}
