import 'package:shared_preferences/shared_preferences.dart';
import 'package:dress_to_impress/main.dart';
import 'package:dress_to_impress/features/profile/shopper_profile.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/features/feed/reels_bindings.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dress_to_impress/features/feed/reels_browse.dart';
import 'package:dress_to_impress/features/shared/niche_theme.dart';
import 'package:dress_to_impress/features/shared/niche_shell.dart';
import 'package:dress_to_impress/features/shared/niche_photo.dart';
import 'package:dress_to_impress/features/profile/niche_welcome.dart';

Map<String, dynamic> item(String id) => {
      'id': id,
      'name': 'Everyday $id',
      'retailer': 'hm',
      'brand': 'H&M',
      'price_usd': 29.99,
      'image_url': '',
      'in_stock': true,
      'description': 'An actual retailer description.',
      'colors': ['Cream'],
      'sizes': [
        {'name': 'M', 'in_stock': true},
        {'name': 'S', 'in_stock': false}
      ]
    };
Future<void> mount(WidgetTester t, Widget child,
    {Size size = const Size(393, 852), bool reduced = true}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
      theme: Niche.theme,
      home: MediaQuery(
          data: MediaQueryData(size: size, disableAnimations: reduced),
          child: Scaffold(body: child))));
  await t.pumpAndSettle();
}

ReelsBrowse feed(
        {List<Map<String, dynamic>>? products,
        Future<void> Function(String, String)? add,
        Future<String?> Function(String)? advise,
        void Function(String?)? closet,
        Future<Map<String, ReelTryOn>> Function(List<String>)? prepare,
        Future<Map<String, ReelTryOn>> Function(List<String>)? status,
        bool active = true}) =>
    ReelsBrowse(
        products: products ?? [item('a'), item('b'), item('c')],
        savedIds: const {},
        onSave: (_, __) async {},
        onAddToCart: add ?? (_, __) async {},
        imageUrl: (s) => s,
        onSizeAdvice: advise,
        onCloset: closet,
        prepareTryOns: prepare,
        loadTryOns: status,
        active: active);

class SafeAreaStore extends StoreController {
  SafeAreaStore() : super(api: Api(), demo: true);
  @override
  Future<void> load() async {
    this.feed = [RankedProduct.fromJson(item('a'))];
    notifyListeners();
  }
}

void main() {
  test(
      'production reels bindings use the shared client and preserve real feed fields',
      () async {
    final requests = <http.Request>[];
    final api = Api(client: MockClient((r) async {
      requests.add(r);
      return http.Response(
          jsonEncode({
            'a': {
              'status': r.method == 'POST' ? 'pending' : 'ready',
              'image_url': r.method == 'POST' ? null : '/static/tryon/a.png',
              'mode': 'ai'
            }
          }),
          200);
    }));
    final bindings = ReelsBindings(api);
    expect((await bindings.prepare(['a']))['a']!.status, 'pending');
    expect(jsonDecode(requests.first.body)['product_ids'], ['a']);
    expect(requests.first.url.path, '/feed/u_demo/tryons');
    expect((await bindings.load(['a']))['a']!.url, '/static/tryon/a.png');
    expect(requests.last.method, 'GET');
    expect(requests.last.url.queryParameters['ids'], 'a');
    final data = browseMap(RankedProduct.fromJson({
      ...item('a'),
      'hero_image_url': '/static/product.jpg',
      'closet_picks': [
        {
          'id': 'own',
          'label': 'My shirt',
          'category': 'top',
          'image_url': '/static/uploads/own.jpg'
        }
      ],
      'tryon': {'status': 'needs_photo'}
    }));
    expect(data['hero_image_url'], '/static/product.jpg');
    expect((data['closet_picks'] as List).single['id'], 'own');
    expect((data['tryon'] as Map)['status'], 'needs_photo');
  });

  test(
      'bundled display/UI fonts have the correct assets and no synthetic display bold',
      () async {
    final manifest =
        jsonDecode(await rootBundle.loadString('FontManifest.json')) as List;
    final serif = manifest.singleWhere((v) => v['family'] == 'YoungSerif');
    expect(serif['fonts'], [
      {'asset': 'assets/fonts/YoungSerif-Regular.ttf', 'weight': 400}
    ]);
    final ui = manifest.singleWhere((v) => v['family'] == 'Manrope');
    expect((ui['fonts'] as List).map((f) => f['weight']), [400, 500, 600, 700]);
    expect(Niche.theme.textTheme.headlineSmall!.fontFamily, 'YoungSerif');
    expect(Niche.theme.textTheme.headlineSmall!.fontWeight, FontWeight.w400);
    expect(Niche.theme.textTheme.bodyMedium!.fontFamily, 'Manrope');
  });
  testWidgets(
      'reels snap vertically; details stay collapsed and actions stay minimal',
      (t) async {
    await mount(t, feed());
    expect(find.text('see more'), findsOneWidget);
    expect(find.text('An actual retailer description.'), findsNothing);
    expect(find.text('Try it on'), findsNothing);
    expect(find.text('Complete the look'), findsNothing);
    await t.drag(
        find.byKey(const ValueKey('product-stream')), const Offset(0, -650));
    await t.pumpAndSettle();
    expect(find.text('Everyday b'), findsOneWidget);
    await t.tap(find.text('see more'));
    await t.pumpAndSettle();
    expect(find.text('An actual retailer description.'), findsOneWidget);
    expect(
        t.widget<NichePhoto>(find.byType(NichePhoto).first).fit, BoxFit.cover);
  });
  testWidgets(
      'carousel clamps at last slide; caption drag changes the shell tab',
      (t) async {
    final shell = PageController();
    addTearDown(shell.dispose);
    await mount(
        t,
        PageView(
            controller: shell,
            children: [feed(), const Center(child: Text('Discover panel'))]));
    final gallery = find.byKey(const ValueKey('reel-photos-a'));
    for (var i = 0; i < 3; i++) {
      await t.drag(gallery, const Offset(-340, 0));
      await t.pumpAndSettle();
    }
    expect(shell.page, 0);
    expect(t.widget<PageView>(gallery).controller!.page, 2);
    await t.drag(find.text('see more'), const Offset(-340, 0));
    await t.pumpAndSettle();
    expect(shell.page, 1);
    expect(find.text('Discover panel'), findsOneWidget);
  });
  testWidgets(
      'unknown size opens available choices before adding and confirms success',
      (t) async {
    final writes = <String>[];
    await mount(
        t,
        feed(
            add: (id, size) async {
              writes.add('$id:$size');
            },
            advise: (_) async => 'S'));
    await t.tap(find.text('Add to cart'));
    await t.pumpAndSettle();
    expect(writes, isEmpty);
    expect(find.text('S'), findsNothing);
    await t.tap(find.text('M'));
    await t.pumpAndSettle();
    expect(writes, ['a:M']);
    expect(find.text('Added ✓'), findsOneWidget);
    await t.pump(const Duration(seconds: 2));
  });
  testWidgets(
      'closet squares use the selected owned image and never a retailer stand-in',
      (t) async {
    String? opened;
    await mount(
        t,
        feed(products: [
          {
            ...item('a'),
            'closet_picks': [
              {
                'id': 'own',
                'label': 'My jeans',
                'image_url': '/static/uploads/mine.jpg'
              },
              {
                'id': 'bad',
                'label': 'Bad fallback',
                'image_url': 'https://cdn.shopify.com/wrong.jpg'
              }
            ]
          }
        ], closet: (id) => opened = id));
    final gallery = find.byKey(const ValueKey('reel-photos-a'));
    await t.drag(gallery, const Offset(-340, 0));
    await t.pumpAndSettle();
    await t.drag(gallery, const Offset(-340, 0));
    await t.pumpAndSettle();
    final urls =
        t.widgetList<NichePhoto>(find.byType(NichePhoto)).map((p) => p.url);
    expect(urls, contains('/static/uploads/mine.jpg'));
    expect(urls, isNot(contains('https://cdn.shopify.com/wrong.jpg')));
    await t.tap(find.text('My jeans'));
    await t.pumpAndSettle();
    expect(opened, 'own');
  });
  testWidgets(
      'pending status polls while visible and stops after ready/disposal',
      (t) async {
    var loads = 0;
    await mount(
        t,
        feed(
            prepare: (ids) async =>
                {'a': (status: 'pending', url: null, mode: null)},
            status: (ids) async {
              loads++;
              return {'a': (status: 'ready', url: '', mode: 'ai')};
            }));
    await t.pump(const Duration(seconds: 3));
    await t.pumpAndSettle();
    expect(loads, 1);
    await t.pump(const Duration(seconds: 6));
    expect(loads, 1);
    await t.pumpWidget(const SizedBox());
    await t.pump(const Duration(seconds: 6));
    expect(loads, 1);
  });

  testWidgets('hidden and background Home never starts prefetch work',
      (t) async {
    final active = ValueNotifier(false);
    addTearDown(active.dispose);
    var prepares = 0;
    await mount(
        t,
        ValueListenableBuilder<bool>(
            valueListenable: active,
            builder: (_, value, __) => feed(
                active: value,
                prepare: (ids) async {
                  prepares++;
                  return {'a': (status: 'ready', url: null, mode: 'ai')};
                })));
    expect(prepares, 0);
    active.value = true;
    await t.pumpAndSettle();
    expect(prepares, 1);
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    active.value = false;
    await t.pump();
    active.value = true;
    await t.pumpAndSettle();
    expect(prepares, 1);
    t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await t.pumpAndSettle();
    expect(prepares, 2);
  });
  for (final size in [const Size(393, 852), const Size(412, 915)]) {
    testWidgets('cart clears the floating bar at ${size.width}x${size.height}',
        (t) async {
      await mount(t, feed(), size: size);
      expect(t.getBottomLeft(find.text('Add to cart')).dy,
          lessThan(size.height - 76));
      expect(t.takeException(), isNull);
    });
  }
  testWidgets(
      'physical bottom inset survives Scaffold and keeps the whole cart button above nav',
      (t) async {
    SharedPreferences.setMockInitialValues({});
    await const ShopperProfile(completed: true).save('u_demo');
    t.view.physicalSize = const Size(393, 852);
    t.view.devicePixelRatio = 1;
    t.view.padding = const FakeViewPadding(top: 62, bottom: 34);
    t.view.viewPadding = const FakeViewPadding(top: 62, bottom: 34);
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    addTearDown(t.view.resetPadding);
    addTearDown(t.view.resetViewPadding);
    await t.pumpWidget(NicheApp(store: SafeAreaStore()));
    await t.pumpAndSettle();
    final button = find.widgetWithText(FilledButton, 'Add to cart');
    expect(t.getBottomLeft(button).dy,
        lessThanOrEqualTo(t.getTopLeft(find.byType(NicheNavigation)).dy - 12));
    expect(t.takeException(), isNull);
  });
  testWidgets(
      'header paints the safe area and reduced motion welcome stays still',
      (t) async {
    final insets = MediaQueryData(
        size: const Size(393, 852),
        padding: const EdgeInsets.only(top: 62, bottom: 34),
        viewPadding: const EdgeInsets.only(top: 62, bottom: 34),
        disableAnimations: true);
    await mount(
        t,
        MediaQuery(
            data: insets,
            child: Column(children: [
              NicheHeader(
                  count: 1,
                  initial: 'Ryan',
                  onLiked: () {},
                  onCart: () {},
                  onCloset: () {},
                  onUser: () {}),
              Expanded(
                  child: NicheWelcome(photos: Future.value([]), onStart: () {}))
            ])));
    expect(t.getSize(find.byType(NicheHeader)).height, 118);
    expect(find.text("Let's go"), findsOneWidget);
    await t.pump(const Duration(seconds: 3));
    expect(t.binding.hasScheduledFrame, false);
    expect(t.takeException(), isNull);
  });
}
