import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/features/product/complete_look_screen.dart';
import 'package:dress_to_impress/features/feed/quick_browse.dart';
import 'package:dress_to_impress/features/shared/feature_ui.dart';

http.Response reply(Object value) => http.Response(jsonEncode(value), 200);
Future<void> mount(WidgetTester t, Widget child) async {
  t.view.physicalSize = const Size(430, 1000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: child));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('complete look joins owned photos by ID and labels catalog gaps',
      (t) async {
    final api = Api(client: MockClient((r) async {
      if (r.url.path.startsWith('/closet/')) {
        return reply([
          {
            'id': 'jeans',
            'user_id': 'u_demo',
            'category': 'bottom',
            'color': 'blue',
            'image_url': 'https://cdn.shopify.com/wrong.jpg',
            'display_image_url': 'https://cdn.shopify.com/wrong.jpg',
            'catalog_image_url': 'https://cdn.shopify.com/wrong.jpg',
            'crop_image_url': '/static/uploads/my-jeans.jpg'
          },
          {
            'id': 'unrelated',
            'user_id': 'u_demo',
            'category': 'top',
            'image_url': '/static/uploads/unrelated.jpg'
          }
        ]);
      }
      if (r.url.path == '/products/shoes') {
        return reply({
          'id': 'shoes',
          'name': 'Catalog sneakers',
          'retailer': 'hm',
          'image_url': 'https://example.test/actual-shoes.jpg',
          'price_usd': 20
        });
      }
      expect(r.url.path, '/complete-look');
      return reply({
        'items': [
          {
            'source': 'closet',
            'id': 'jeans',
            'category': 'bottom',
            'label': 'My jeans'
          },
          {
            'source': 'catalog',
            'id': 'shoes',
            'category': 'shoes',
            'label': 'Catalog sneakers'
          }
        ],
        'new_items_total_usd': 20,
        'missing': [],
        'primary_style': 'streetwear',
        'fit_score': {
          'score': 82,
          'primary_style': 'streetwear',
          'verdict': '82 as streetwear: balanced everyday look',
          'notes': [],
          'criteria': [
            {'name': 'color', 'score_10': 8, 'note': 'Works together.'}
          ]
        }
      });
    }));
    await mount(t,
        CompleteLookScreen(api: api, productId: 'anchor', onProduct: (_) {}));
    final urls = t
        .widgetList<PiecePhoto>(find.byType(PiecePhoto))
        .map((p) => p.url)
        .toList();
    expect(urls, [
      api.imageProxyUrl('/static/uploads/my-jeans.jpg'),
      'https://example.test/actual-shoes.jpg'
    ]);
    expect(find.textContaining('Already in your closet'), findsOneWidget);
    expect(find.textContaining('Catalog piece'), findsOneWidget);
    await t.scrollUntilVisible(find.text('As streetwear'), 250);
    expect(find.text('Color · 8/10'), findsOneWidget);
    expect(find.text('balanced everyday look'), findsOneWidget);
  });

  testWidgets('missing closet photos never substitute catalog pictures',
      (t) async {
    final api = Api(client: MockClient((r) async {
      if (r.url.path.startsWith('/closet/')) {
        return http.Response('offline', 503);
      }
      return reply({
        'items': [
          {
            'source': 'closet',
            'id': 'lost',
            'category': 'top',
            'label': 'My shirt'
          }
        ],
        'missing': [],
        'new_items_total_usd': 0
      });
    }));
    await mount(t,
        CompleteLookScreen(api: api, productId: 'anchor', onProduct: (_) {}));
    expect(t.widget<PiecePhoto>(find.byType(PiecePhoto)).url, '');
    expect(find.text('My shirt'), findsOneWidget);
    expect(find.textContaining('Some photos could not load'), findsOneWidget);
  });

  testWidgets(
      'try-on compares the actual source photo without another generation',
      (t) async {
    var generations = 0;
    await mount(
        t,
        Scaffold(
            body: QuickBrowse(
                products: [
              {
                'id': 'p',
                'name': 'Tee',
                'price_usd': 20,
                'image_url': 'https://example.test/catalog.jpg',
                'images': [
                  {'url': 'https://example.test/catalog.jpg'}
                ],
                'sizes': [
                  {'name': 'M', 'in_stock': true}
                ]
              }
            ],
                savedIds: const {},
                imageUrl: (s) => s,
                onSave: (_, __) async {},
                onAddToCart: (_, __) async {},
                onTryOn: (_) async {
                  generations++;
                  return (
                    url: 'https://example.test/result.jpg',
                    label: 'Your AI try-on',
                    sourcePhotoUrl: 'https://example.test/source.jpg'
                  );
                })));
    await t.ensureVisible(find.text('Try it on'));
    await t.tap(find.text('Try it on'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Compare with original'));
    await t.tap(find.text('Compare with original'));
    await t.pumpAndSettle();
    expect(find.text('Your original photo'), findsOneWidget);
    final source = t.widgetList<Image>(find.byType(Image)).where((i) =>
        i.image is NetworkImage &&
        (i.image as NetworkImage).url.endsWith('/source.jpg'));
    expect(source.single.fit, BoxFit.contain);
    await t.tap(find.text('Show try-on'));
    await t.pumpAndSettle();
    expect(find.text('Your AI try-on'), findsOneWidget);
    expect(generations, 1);
  });
}
