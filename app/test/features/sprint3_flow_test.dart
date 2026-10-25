import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/features/closet/closet_screen.dart';
import 'package:dress_to_impress/features/shared/feature_ui.dart';
import 'package:dress_to_impress/features/shared/pick_photo.dart';
import 'package:dress_to_impress/features/shared/natural_photo_frame.dart';
import 'package:dress_to_impress/features/social/comments_sheet.dart';

http.Response reply(Object v) => http.Response(jsonEncode(v), 200);
Map<String, dynamic> owned(String id) => {
      'id': id,
      'user_id': 'u_demo',
      'label': 'My $id',
      'category': 'top',
      'color': 'blue',
      'brand': 'My brand',
      'image_url': 'https://cdn.shopify.com/catalog.jpg',
      'display_image_url': 'https://cdn.shopify.com/catalog.jpg',
      'catalog_image_url': 'https://cdn.shopify.com/catalog.jpg',
      'crop_image_url': '/static/uploads/$id.jpg',
      'product_id': 'matched',
      'worn_in': [
        {'photo_url': '/static/uploads/outfit.jpg', 'source': 'closet'}
      ]
    };
PickedPhoto photo() => PickedPhoto(
    Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]), 'image/png');
Future<void> mount(WidgetTester t, Widget child) async {
  t.view.physicalSize = const Size(430, 900);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: child));
  await t.pumpAndSettle();
}

void main() {
  test('photo layout keeps wide images whole and caps only tall portraits', () {
    expect(postPhotoAspect(1600, 900), closeTo(16 / 9, .001));
    expect(postPhotoAspect(900, 1600), 9 / 16);
    expect(postPhotoAspect(500, 2500), 9 / 16);
    expect(postPhotoAspect(800, 1000), .8);
    expect(postPhotoAspect(0, 0), 1);
  });
  test('owned picture uses crop or clean shot and never catalog fallback', () {
    final p = ClosetItem.fromJson(owned('shirt'));
    expect(ownedClosetPhoto(p), '/static/uploads/shirt.jpg');
    expect(
        ownedClosetPhoto(
            ClosetItem.fromJson({...owned('shirt'), 'crop_image_url': null})),
        '');
    expect(
        ownedClosetPhoto(ClosetItem.fromJson({
          ...owned('shirt'),
          'display_image_url': '/static/clean/shirt.jpg'
        })),
        '/static/clean/shirt.jpg');
  });
  for (final choice in ['A piece', 'An outfit']) {
    testWidgets('$choice detects every garment in multiple photos', (t) async {
      var uploaded = false;
      final client = Api(client: MockClient((r) async {
        if (r.method == 'GET') {
          return reply(uploaded ? [owned('shirt'), owned('jacket')] : []);
        }
        expect(r.url.path, '/closet/upload');
        final body = latin1.decode(r.bodyBytes);
        expect(body, contains('name="kind"\r\n\r\noutfit'));
        expect(RegExp('name="files"').allMatches(body).length, 2);
        expect(body, contains('image/png'));
        uploaded = true;
        return reply({
          'added': [owned('shirt'), owned('jacket')],
          'merged': [],
          'skipped': 0
        });
      }));
      await mount(
          t,
          ClosetScreen(
              api: client, photosPicker: () async => [photo(), photo()]));
      await t.tap(find.text('Add to closet'));
      await t.pumpAndSettle();
      await t.tap(find.text(choice));
      await t.pumpAndSettle();
      expect(uploaded, true);
      expect(find.textContaining('2 new pieces'), findsOneWidget);
      expect(find.text('My shirt'), findsOneWidget);
      expect(find.text('My jacket'), findsOneWidget);
      expect(
          t
              .widgetList<PiecePhoto>(find.byType(PiecePhoto))
              .every((p) => !p.url.contains('catalog.jpg')),
          true);
    });
  }
  testWidgets('canceling photo selection performs no upload', (t) async {
    var uploads = 0;
    final client = Api(client: MockClient((r) async {
      if (r.method != 'GET') uploads++;
      return reply([]);
    }));
    await mount(t, ClosetScreen(api: client, photosPicker: () async => []));
    await t.tap(find.text('Add to closet'));
    await t.pumpAndSettle();
    await t.tap(find.text('An outfit'));
    await t.pumpAndSettle();
    expect(uploads, 0);
  });
  testWidgets(
      'outfit photo groups its linked owned pieces and opens honest detail',
      (t) async {
    final client = Api(
        client:
            MockClient((r) async => reply([owned('shirt'), owned('jacket')])));
    await mount(t, ClosetScreen(api: client));
    await t.tap(find.text('Outfits'));
    await t.pumpAndSettle();
    expect(find.text('2 pieces'), findsOneWidget);
    await t.tap(find.text('2 pieces'));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(ActionChip, 'My shirt'));
    await t.pumpAndSettle();
    expect(find.text('Edit piece'), findsOneWidget);
    expect(find.text('My brand'), findsOneWidget);
    expect(
        t
            .widgetList<PiecePhoto>(find.byType(PiecePhoto))
            .every((p) => !p.url.contains('catalog.jpg')),
        true);
  });
  testWidgets(
      'comments stay ordered and input stays above keyboard while sending',
      (t) async {
    FitCheckComment? added;
    final client = Api(client: MockClient((r) async {
      expect(r.url.path, '/fitcheck/post/comments');
      expect(jsonDecode(r.body)['text'], 'Third');
      return reply({
        'id': '3',
        'user_id': 'u_demo',
        'text': 'Third',
        'created_at': '2026-10-24T12:02:00Z'
      });
    }));
    await mount(
        t,
        Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () => showModalBottomSheet<void>(
                        context: context,
                        isScrollControlled: true,
                        builder: (_) => CommentsSheet(
                            api: client,
                            postId: 'post',
                            initial: const [
                              FitCheckComment(
                                  id: '2',
                                  userId: 'other',
                                  text: 'Second',
                                  createdAt: '2026-10-24T12:01:00Z'),
                              FitCheckComment(
                                  id: '1',
                                  userId: 'other',
                                  text: 'First',
                                  createdAt: '2026-10-24T12:00:00Z')
                            ],
                            onAdded: (c) => added = c)),
                    child: const Text('Open comments')))));
    await t.tap(find.text('Open comments'));
    await t.pumpAndSettle();
    expect(t.getTopLeft(find.text('First')).dy,
        lessThan(t.getTopLeft(find.text('Second')).dy));
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(t.getBottomRight(find.byTooltip('Send comment')).dy,
        lessThanOrEqualTo(600));
    await t.enterText(
        find.widgetWithText(TextField, 'Add a comment…'), 'Third');
    await t.tap(find.byTooltip('Send comment'));
    await t.pumpAndSettle();
    expect(added?.text, 'Third');
    expect(find.text('Third'), findsOneWidget);
  });
}
