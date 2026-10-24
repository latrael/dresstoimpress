import 'dart:async';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:dress_to_impress/features/search/catalog_search.dart';
import 'package:dress_to_impress/features/feed/quick_browse.dart';
import 'package:dress_to_impress/features/product/try_on.dart';
import 'package:dress_to_impress/features/product/complete_look_screen.dart';
import 'package:dress_to_impress/features/profile/onboarding_screen.dart';
import 'package:dress_to_impress/features/profile/profile_screen.dart';
import 'package:dress_to_impress/features/social/social_feed.dart';
import 'package:dress_to_impress/features/closet/closet_screen.dart';
import 'package:dress_to_impress/features/shared/pick_photo.dart';

Map<String, dynamic> piece(String id) => {
      'id': id,
      'name': 'Piece $id',
      'retailer': 'hm',
      'category': 'top',
      'price_usd': 20,
      'image_url': 'https://example.test/$id.jpg',
      'images': [
        {'url': 'https://example.test/$id.jpg'}
      ],
      'in_stock': true,
      'sizes': [
        {'name': 'S', 'in_stock': true},
        {'name': 'M', 'in_stock': false}
      ],
      'description': 'Retailer description',
    };
Map<String, dynamic> user() => {
      'id': 'u_demo',
      'display_name': 'Demo',
      'body_photo_url': '/static/uploads/body.jpg'
    };
Map<String, dynamic> score() => {
      'score': 85,
      'verdict': 'Works together',
      'notes': ['Colors go together.', 'Balanced outfit.'],
      'breakdown': {
        'color': 35,
        'pattern': 20,
        'formality': 15,
        'completeness': 15
      }
    };
Map<String, dynamic> closetItem() => {
      'id': 'ci_new',
      'user_id': 'u_demo',
      'label': 'White shirt',
      'category': 'top',
      'color': 'white',
      'image_url': '/static/uploads/shirt.png',
      'duplicate_of': 'ci_old'
    };
Map<String, dynamic> postJson({bool liked = false}) => {
      'id': 'post',
      'user_id': 'u_demo',
      'photo_url': '',
      'caption': 'My outfit',
      'tagged': [
        {'label': 'Shirt', 'product_id': 'p', 'category': 'top'}
      ],
      'likes': [],
      'comments': [],
      'liked_by_me': liked,
      'like_count': liked ? 1 : 0
    };
http.Response json(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status);
Api mockApi(Future<http.Response> Function(http.Request) handle) => Api(
    client: MockClient(handle))
  ..settings =
      const Settings(baseUrl: 'https://api.example.test', apiKey: 'test-only');
final testPhoto = PickedPhoto(
    Uint8List.fromList(base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==')),
    'image/png');

Future<void> mount(WidgetTester tester, Widget child) async {
  tester.view.physicalSize = const Size(440, 1100);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: child));
  await tester.pumpAndSettle();
}

Future<void> tap(WidgetTester tester, String text) async {
  await tester.ensureVisible(find.text(text).last);
  await tester.pumpAndSettle();
  await tester.tap(find.text(text).last);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test(
      'catalog search pages beyond feed and keeps results after next-page failure',
      () async {
    var attempts = 0;
    final api = mockApi((r) async {
      expect(r.url.path, '/products');
      expect(r.url.queryParameters['q'], 'jeans');
      final offset = r.url.queryParameters['offset'];
      if (offset == '0') {
        return json({
          'items': [piece('a')],
          'total': 3,
          'limit': 1,
          'offset': 0,
          'next_offset': 1
        });
      }
      if (attempts++ == 0) return json({'detail': 'failed'}, 500);
      return json({
        'items': [piece('b'), piece('c')],
        'total': 3,
        'limit': 2,
        'offset': 1,
        'next_offset': null
      });
    });
    final search = CatalogSearch(api);
    addTearDown(search.dispose);
    await search.search('jeans');
    await search.more();
    expect(search.cards.map((c) => c.id), ['a']);
    expect(search.error, isNotNull);
    expect(search.nextOffset, 1);
    await search.more();
    expect(search.cards.map((c) => c.id), ['a', 'b', 'c']);
    expect(search.nextOffset, isNull);
  });
  test('late catalog response cannot replace newer query', () async {
    final old = Completer<http.Response>();
    final api = mockApi((r) async => r.url.queryParameters['q'] == 'old'
        ? old.future
        : json({
            'items': [piece('new')],
            'total': 1,
            'next_offset': null
          }));
    final search = CatalogSearch(api);
    addTearDown(search.dispose);
    final pending = search.search('old');
    await search.search('new');
    old.complete(json({
      'items': [piece('old')],
      'total': 1
    }));
    await pending;
    expect(search.cards.single.id, 'new');
    expect(search.loading, false);
  });
  testWidgets('unavailable size recommendation never selects a disabled size',
      (tester) async {
    await mount(
        tester,
        Scaffold(
            body: QuickBrowse(
                products: [piece('a')],
                savedIds: const {},
                onSave: (_, saved) async {},
                onAddToCart: (_, size) async {},
                imageUrl: (s) => s,
                onSizeAdvice: (_) async => 'M')));
    await tap(tester, 'Find my size');
    expect(
        tester
            .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'M'))
            .selected,
        false);
    expect(find.textContaining('no longer available'), findsOneWidget);
  });
  testWidgets(
      'three products get separate generated slides within the photo carousel',
      (tester) async {
    final generated = <String>[];
    await mount(
        tester,
        Scaffold(
            body: QuickBrowse(
                products: [piece('a'), piece('b'), piece('c')],
                savedIds: const {},
                onSave: (_, saved) async {},
                onAddToCart: (_, size) async {},
                imageUrl: (s) => s,
                onTryOn: (id) async {
                  generated.add(id);
                  return (
                    url: 'https://example.test/$id-board.jpg',
                    label: 'Outfit board · collage, not a photo of you'
                  );
                })));
    for (final id in ['a', 'b', 'c']) {
      final product = find.byKey(ValueKey('details-$id'));
      final tryOn =
          find.descendant(of: product, matching: find.text('Try it on'));
      await tester.ensureVisible(tryOn);
      await tester.pumpAndSettle();
      await tester.tap(tryOn);
      await tester.pumpAndSettle();
      expect(
          find.descendant(
              of: product,
              matching:
                  find.text('Outfit board · collage, not a photo of you')),
          findsOneWidget);
      expect(
          tester
              .widget<PageView>(find.byKey(ValueKey('photos-$id')))
              .controller!
              .page,
          1);
      await tester.ensureVisible(find.descendant(
          of: product, matching: find.text('Retailer description')));
      await tester.pumpAndSettle();
      await tester.drag(
          find.descendant(
              of: product, matching: find.text('Retailer description')),
          const Offset(250, 0));
      await tester.pumpAndSettle();
      expect(
          tester
              .widget<PageView>(find.byKey(ValueKey('photos-$id')))
              .controller!
              .page,
          1);
    }
    expect(generated, ['a', 'b', 'c']);
  });
  testWidgets('try-on without a body photo can be canceled without uploading',
      (tester) async {
    var writes = 0, picked = false;
    final api = mockApi((r) async {
      if (r.method != 'GET') writes++;
      return json({'id': 'u_demo', 'display_name': 'Demo'});
    });
    await mount(
        tester,
        Scaffold(
            body: Builder(
                builder: (context) => TextButton(
                    onPressed: () =>
                        requestTryOn(context, api, 'a', picker: () async {
                          picked = true;
                          return testPhoto;
                        }),
                    child: const Text('Try')))));
    await tap(tester, 'Try');
    await tap(tester, 'Later');
    expect(writes, 0);
    expect(picked, false);
  });
  testWidgets('try-on uses existing photo and labels collage response honestly',
      (tester) async {
    final paths = <String>[];
    ({String url, String label})? result;
    final api = mockApi((r) async {
      paths.add(r.url.path);
      return r.method == 'GET'
          ? json(user())
          : json({
              'image_url': '/static/tryon/board.png',
              'mode': 'collage',
              'cached': true
            });
    });
    await mount(
        tester,
        Scaffold(
            body: Builder(
                builder: (context) => TextButton(
                    onPressed: () async {
                      result = await requestTryOn(context, api, 'a');
                    },
                    child: const Text('Try')))));
    await tap(tester, 'Try');
    expect(result!.label, contains('not a photo of you'));
    expect(paths, ['/users/u_demo', '/tryon']);
  });
  testWidgets(
      'complete look scores catalog and owned items through their distinct fields',
      (tester) async {
    final api = mockApi((r) async {
      if (r.url.path == '/complete-look') {
        return json({
          'items': [
            {
              'source': 'closet',
              'id': 'ci_1',
              'category': 'bottom',
              'label': 'My jeans'
            },
            {
              'source': 'catalog',
              'id': 'shoe',
              'category': 'shoes',
              'label': 'White shoes'
            }
          ],
          'new_items_total_usd': 35,
          'missing': ['outerwear']
        });
      }
      expect(r.url.path, '/ai/fit-score');
      final body = jsonDecode(r.body) as Map;
      expect(body['product_ids'], ['anchor', 'shoe']);
      expect(body['closet_item_ids'], ['ci_1']);
      return json(score());
    });
    await mount(tester,
        CompleteLookScreen(api: api, productId: 'anchor', onProduct: (_) {}));
    expect(find.textContaining('Already in your closet'), findsOneWidget);
    await tap(tester, 'Get Fit Score');
    expect(find.text('Fit Score · 85/100'), findsOneWidget);
    expect(find.textContaining('Still missing'), findsOneWidget);
  });
  testWidgets('onboarding sends free text and shows parsed saved budgets',
      (tester) async {
    var refreshed = false;
    final api = mockApi((r) async {
      if (r.method == 'GET') return json(user());
      if (r.method == 'PATCH' && r.url.path.endsWith('/body-profile')) {
        return json({'height_cm': 0});
      }
      if (r.method == 'PATCH') return json(user());
      expect(r.url.path, '/onboarding');
      expect(jsonDecode(r.body)['text'], r'Y2K tops under $40, regular fit');
      return json({
        'user': {
          ...user(),
          'price_ranges': {
            'top': [0, 40]
          }
        },
        'parsed': {
          'styles': ['y2k'],
          'budgets': {
            'top': [0, 40]
          },
          'unmatched': ''
        }
      });
    });
    await mount(
        tester,
        OnboardingScreen(
            api: api,
            onSaved: () async {
              refreshed = true;
            }));
    await tester.enterText(find.widgetWithText(TextField, 'Style and budget'),
        r'Y2K tops under $40');
    await tester.scrollUntilVisible(find.text('Save preferences'), 500,
        scrollable: find.byType(Scrollable).first);
    await tap(tester, 'Save preferences');
    expect(refreshed, true);
    await tester.scrollUntilVisible(find.text(r'top · $0–$40'), 200,
        scrollable: find.byType(Scrollable).first);
    expect(find.text(r'top · $0–$40'), findsOneWidget);
  });
  testWidgets('Fit Check like and comment reflect only successful responses',
      (tester) async {
    final paths = <String>[];
    final api = mockApi((r) async {
      paths.add(r.url.path);
      if (r.url.path.endsWith('/like')) {
        return json({'post_id': 'post', 'liked': true, 'like_count': 1});
      }
      expect(jsonDecode(r.body)['text'], 'Great fit');
      return json({
        'id': 'comment',
        'user_id': 'u_demo',
        'text': 'Great fit',
        'comment_count': 1
      });
    });
    await mount(
        tester,
        Scaffold(
            body: SingleChildScrollView(
                child: FitPostCard(
                    post: FitCheckPost.fromJson(postJson()),
                    api: api,
                    onShop: (_) {}))));
    await tester.tap(find.byIcon(Icons.favorite_border));
    await tester.pumpAndSettle();
    expect(find.text('1'), findsOneWidget);
    await tester.enterText(
        find.widgetWithText(TextField, 'Add a comment'), 'Great fit');
    await tester.ensureVisible(find.byTooltip('Send comment'));
    await tester.tap(find.byTooltip('Send comment'));
    await tester.pumpAndSettle();
    expect(find.text('u_demo · Great fit'), findsOneWidget);
    expect(paths, ['/fitcheck/post/like', '/fitcheck/post/comments']);
  });
  testWidgets('editing outfit labels preserves tagged product identity',
      (tester) async {
    final api = mockApi((r) async {
      if (r.method == 'GET') return json(piece('p'));
      expect(r.url.path, '/fitcheck/post/tags');
      final tags = jsonDecode(r.body)['tagged'] as List;
      expect(tags.single['label'], 'Blue shirt');
      expect(tags.single['product_id'], 'p');
      return json({...postJson(), 'tagged': tags});
    });
    await mount(
        tester,
        Scaffold(
            body: SingleChildScrollView(
                child: FitPostCard(
                    post: FitCheckPost.fromJson(postJson()),
                    api: api,
                    onShop: (_) {}))));
    await tap(tester, 'Edit tags');
    await tester.enterText(
        find.widgetWithText(TextField, 'Piece 1'), 'Blue shirt');
    await tap(tester, 'Save tags');
    await tester.tap(find.bySemanticsLabel('Show outfit tags'));
    await tester.pumpAndSettle();
    expect(tester.widget<CatalogTag>(find.byType(CatalogTag)).tag.label,
        'Blue shirt');
  });
  testWidgets(
      'closet uploads real MIME, keeps duplicate and removes only after confirmation',
      (tester) async {
    var uploaded = false, deleted = false;
    final api = mockApi((r) async {
      if (r.method == 'GET') {
        return json(uploaded && !deleted ? [closetItem()] : []);
      }
      if (r.method == 'POST') {
        expect(utf8.decode(r.bodyBytes, allowMalformed: true),
            contains('Content-Type: image/png'));
        uploaded = true;
        return json(closetItem());
      }
      expect(r.url.path, '/closet/u_demo/ci_new');
      deleted = true;
      return json({'deleted': 'ci_new'});
    });
    await mount(tester, ClosetScreen(api: api, picker: () async => testPhoto));
    await tap(tester, 'Add a piece');
    expect(find.textContaining('Possible duplicates'), findsOneWidget);
    expect(find.text('White shirt'), findsOneWidget);
    await tester.tap(find.byTooltip('Remove closet piece'));
    await tester.pumpAndSettle();
    await tap(tester, 'Keep');
    expect(deleted, false);
    await tester.tap(find.byTooltip('Remove closet piece'));
    await tester.pumpAndSettle();
    await tap(tester, 'Remove');
    expect(deleted, true);
  });
  testWidgets(
      'profile displays Style DNA and handles apply 409 without claiming saved',
      (tester) async {
    final api = mockApi((r) async {
      if (r.method == 'POST') return json({'detail': 'need five likes'}, 409);
      if (r.url.path.endsWith('/style')) {
        return json({
          'headline': 'Streetwear favorites',
          'styles': [
            {'tag': 'streetwear', 'share': 1.0}
          ],
          'sample_size': {'liked': 2},
          'palette': [
            {
              'name': 'Black',
              'family': 'neutral',
              'hex': '#000000',
              'share': 1.0
            }
          ]
        });
      }
      return json(user());
    });
    await mount(tester, ProfileScreen(api: api, onChanged: () async {}));
    expect(find.text('Streetwear favorites'), findsOneWidget);
    await tap(tester, 'Use learned budgets');
    expect(find.textContaining('at least five'), findsOneWidget);
    expect(find.text('Your learned budgets are saved.'), findsNothing);
  });
  testWidgets(
      'Fit Check creation sends selected photo MIME and caption only on Post',
      (tester) async {
    var writes = 0;
    bool? created;
    final api = mockApi((r) async {
      writes++;
      expect(r.url.path, '/fitcheck');
      final multipart = utf8.decode(r.bodyBytes, allowMalformed: true);
      expect(multipart, contains('Content-Type: image/png'));
      expect(multipart, contains('Local test caption'));
      return json(postJson());
    });
    await mount(
        tester,
        Scaffold(
            body: Builder(
                builder: (context) => TextButton(
                    onPressed: () async {
                      created = await Navigator.push<bool>(
                          context,
                          MaterialPageRoute(
                              builder: (_) => CreateFitCheckScreen(
                                  api: api, picker: () async => testPhoto)));
                    },
                    child: const Text('Create')))));
    await tap(tester, 'Create');
    await tap(tester, 'Choose outfit photo');
    expect(writes, 0);
    await tester.enterText(
        find.widgetWithText(TextField, 'Caption'), 'Local test caption');
    await tap(tester, 'Post to Inspo');
    expect(writes, 1);
    expect(created, true);
  });
  testWidgets('canceling a photo picker leaves Fit Check unpublished',
      (tester) async {
    var writes = 0;
    final api = mockApi((r) async {
      writes++;
      return json(postJson());
    });
    await mount(
        tester, CreateFitCheckScreen(api: api, picker: () async => null));
    await tap(tester, 'Choose outfit photo');
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Post to Inspo'))
            .onPressed,
        isNull);
    expect(writes, 0);
  });
  testWidgets('failed comment keeps draft and never adds a success comment',
      (tester) async {
    final api = mockApi((r) async => json({'detail': 'unavailable'}, 502));
    await mount(
        tester,
        Scaffold(
            body: SingleChildScrollView(
                child: FitPostCard(
                    post: FitCheckPost.fromJson(postJson()),
                    api: api,
                    onShop: (_) {}))));
    await tester.enterText(
        find.widgetWithText(TextField, 'Add a comment'), 'Keep this draft');
    await tester.ensureVisible(find.byTooltip('Send comment'));
    await tester.tap(find.byTooltip('Send comment'));
    await tester.pumpAndSettle();
    expect(find.text('u_demo · Keep this draft'), findsNothing);
    expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, 'Add a comment'))
            .controller!
            .text,
        'Keep this draft');
    expect(find.textContaining('Could not send comment'), findsOneWidget);
  });
}
