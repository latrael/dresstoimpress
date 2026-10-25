import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/features/social/social_feed.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response utf8Json(Object body) =>
    http.Response.bytes(utf8.encode(jsonEncode(body)), 200,
        headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  test('post parses reactions in display order and the viewer reaction', () {
    final post = FitCheckPost.fromJson({
      'id': 'p',
      'user_id': 'u',
      'photo_url': '',
      'reactions': {'💯': 2, '🔥': 1, '🙃': 9},
      'my_reaction': '🔥'
    });
    expect(post.reactions.keys.toList(), ['🔥', '💯']);
    expect(post.reactionTotal, 3);
    expect(post.myReaction, '🔥');
  });

  testWidgets('find similar sheet lists your own pieces before pieces to shop',
      (t) async {
    final paths = <String>[];
    final api = Api(client: MockClient((r) async {
      paths.add(r.url.path);
      return utf8Json([
        {
          'tag': {'label': 'white baby tee', 'category': 'top'},
          'closet': [
            {
              'id': 'ci_tee',
              'user_id': 'u_demo',
              'label': 'white crew tee',
              'category': 'top',
              'color': 'white',
              'image_url': '/static/uploads/tee.jpg',
              'crop_image_url': '/static/uploads/tee.jpg'
            }
          ],
          'products': [
            {
              'id': 'hm:tee',
              'retailer': 'hm',
              'name': 'Baby Tee',
              'category': 'top',
              'price_usd': 9.99,
              'image_url': 'https://image.hm.com/tee.jpg',
              'product_url': 'https://hm.com/tee'
            }
          ]
        }
      ]);
    }));
    t.view.physicalSize = const Size(430, 900);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final shopped = <List<RankedProduct>>[];
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: FindSimilarSheet(
                api: api,
                post:
                    const FitCheckPost(id: 'p', userId: 'other', photoUrl: ''),
                onShop: shopped.add))));
    await t.pumpAndSettle();
    expect(paths, ['/fitcheck/p/similar']);
    expect(find.text('White baby tee'), findsOneWidget);
    expect(find.text('1 in your closet · 1 to shop'), findsOneWidget);
    final own = t.getTopLeft(find.byKey(const ValueKey('similar-own-ci_tee')));
    final shop =
        t.getTopLeft(find.byKey(const ValueKey('similar-shop-hm:tee')));
    expect(own.dy < shop.dy, true);
    expect(find.text('YOU ALREADY OWN'), findsOneWidget);
    expect(find.text('Shop the whole look'), findsOneWidget);
  });
}
