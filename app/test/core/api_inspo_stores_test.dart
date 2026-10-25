// Core (Adam), sprint 3: idempotent PUT like, paged comments with author names, photo size, GET /stores.
// Mirrors the backend JSON in backend/app/commerce/fitcheck.py and router.py; "old server" cases check
// that missing fields fall back instead of throwing.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Api _api(List<http.Request> seen, Object Function(http.Request) reply) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

Map<String, dynamic> _comment(String id, String uid, {String? name, String text = 'fire'}) => {
      'id': id, 'user_id': uid, 'text': text, 'created_at': '2026-10-24T01:00:00Z',
      if (name != null) 'author': {'id': uid, 'display_name': name},
    };

void main() {
  group('setFitCheckLike', () {
    test('PUTs {user_id, liked} and parses LikeResult', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => {'post_id': 'p1', 'liked': true, 'like_count': 3});
      final r = await api.setFitCheckLike('p1', liked: true);
      final req = seen.single;
      expect(req.method, 'PUT');
      expect(req.url.path, '/fitcheck/p1/like');
      expect(req.headers['X-DTI-Key'], 'k');
      expect(jsonDecode(req.body), {'user_id': 'u_demo', 'liked': true});
      expect((r.postId, r.liked, r.likeCount), ('p1', true, 3));
    });

    test('liked: false is sent (not dropped as a null) and ids are escaped', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => {'post_id': 'p/2', 'liked': false, 'like_count': 0});
      final r = await api.setFitCheckLike('p/2', liked: false);
      expect(seen.single.url.path, '/fitcheck/p%2F2/like');
      expect(jsonDecode(seen.single.body), {'user_id': 'u_demo', 'liked': false});
      expect(r.liked, false);
      expect(r.likeCount, 0);
    });
  });

  group('fitCheckComments', () {
    test('first page: GET with user_id + limit, no before; parses count, authors and cursor', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => {
            'post_id': 'p1',
            'comments': [_comment('c2', 'u_ryan', name: 'Ryan'), _comment('c3', 'u_nabil', name: 'Nabil')],
            'next_before': 'c2',
            'comment_count': 3,
          });
      final page = await api.fitCheckComments('p1');
      final req = seen.single;
      expect(req.method, 'GET');
      expect(req.url.path, '/fitcheck/p1/comments');
      expect(req.url.queryParameters, {'user_id': 'u_demo', 'limit': '20'});
      expect(page.postId, 'p1');
      expect(page.commentCount, 3);
      expect(page.nextBefore, 'c2');
      expect(page.hasMore, true);
      expect(page.comments.map((c) => c.id), ['c2', 'c3']);
      expect(page.comments.map((c) => c.authorName), ['Ryan', 'Nabil']);
      expect(page.comments.first.userId, 'u_ryan');
    });

    test('older page: sends before + limit; last page has a null cursor', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => {
            'post_id': 'p1', 'comments': [_comment('c1', 'u_adam', name: 'Adam')], 'next_before': null, 'comment_count': 3,
          });
      final page = await api.fitCheckComments('p1', limit: 5, before: 'c2');
      expect(seen.single.url.queryParameters, {'user_id': 'u_demo', 'limit': '5', 'before': 'c2'});
      expect(page.comments.single.authorName, 'Adam');
      expect(page.nextBefore, isNull);
      expect(page.hasMore, false);
    });

    test('old server / sparse JSON: empty page, no count, author falls back to user_id', () {
      final page = FitCheckCommentsPage.fromJson({'post_id': 'p1'});
      expect((page.postId, page.commentCount, page.nextBefore), ('p1', null, null));
      expect(page.comments, isEmpty);
      final noAuthor = FitCheckComment.fromJson(_comment('c9', 'u_old'));
      expect(noAuthor.authorName, 'u_old');
      final emptyName = FitCheckComment.fromJson({'id': 'c8', 'user_id': 'u_x', 'text': 't', 'author': {'id': 'u_x'}});
      expect(emptyName.authorName, 'u_x');
    });
  });

  group('comment POST + post photo size', () {
    test('commentFitCheck parses author and comment_count', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => {..._comment('c4', 'u_demo', name: 'Demo', text: 'clean'), 'comment_count': 4});
      final c = await api.commentFitCheck('p1', 'clean');
      expect(seen.single.method, 'POST');
      expect(jsonDecode(seen.single.body), {'user_id': 'u_demo', 'text': 'clean'});
      expect((c.id, c.authorName, c.commentCount, c.text), ('c4', 'Demo', 4, 'clean'));
    });

    test('FitCheckPost reads photo_w / photo_h; embedded comments get author names', () {
      final post = FitCheckPost.fromJson({
        'id': 'p1', 'user_id': 'u_ryan', 'photo_url': '/static/uploads/a.jpg', 'photo_w': 1080, 'photo_h': 1920,
        'author': {'id': 'u_ryan', 'display_name': 'Ryan'}, 'like_count': 1, 'liked_by_me': false, 'comment_count': 1,
        'comments': [_comment('c1', 'u_nabil', name: 'Nabil')],
      });
      expect((post.photoWidth, post.photoHeight), (1080, 1920));
      expect(post.photoAspectRatio, closeTo(0.5625, 1e-9));
      expect(post.authorName, 'Ryan');
      expect(post.comments.single.authorName, 'Nabil');
    });

    test('old posts: photo size null (explicit nulls or missing keys), ratio null, no crash', () {
      final explicit = FitCheckPost.fromJson({'id': 'p0', 'user_id': 'u', 'photo_url': 'x', 'photo_w': null, 'photo_h': null});
      final missing = FitCheckPost.fromJson({'id': 'p0', 'user_id': 'u', 'photo_url': 'x'});
      for (final p in [explicit, missing]) {
        expect(p.photoWidth, isNull);
        expect(p.photoHeight, isNull);
        expect(p.photoAspectRatio, isNull);
      }
      final zero = FitCheckPost.fromJson({'id': 'p0', 'user_id': 'u', 'photo_url': 'x', 'photo_w': 0, 'photo_h': 10});
      expect(zero.photoAspectRatio, isNull);
    });
  });

  group('stores', () {
    setUp(() => StoreInfo.remember(const []));

    test('GET /stores parses StoreInfo list in server order and fills nameFor', () async {
      final seen = <http.Request>[];
      final api = _api(seen, (_) => [
            {'id': 'hm', 'name': 'H&M', 'count': 120, 'departments': {'men': 70, 'women': 50}},
            {'id': 'stussy', 'name': 'Stüssy', 'count': 12, 'departments': {'unisex': 12}},
          ]);
      expect(StoreInfo.nameFor('hm'), 'hm'); // before the call: the id
      expect(StoreInfo.knows('hm'), false);
      final stores = await api.stores();
      expect(seen.single.method, 'GET');
      expect(seen.single.url.path, '/stores');
      expect(seen.single.headers['X-DTI-Key'], 'k');
      expect(stores.map((s) => s.id), ['hm', 'stussy']);
      expect(stores.first.count, 120);
      expect(stores.first.departments, {'men': 70, 'women': 50});
      expect(StoreInfo.nameFor('hm'), 'H&M');
      expect(StoreInfo.nameFor('stussy'), 'Stüssy');
      expect(StoreInfo.knows('hm'), true);
      expect(StoreInfo.nameFor('unknownshop'), 'unknownshop'); // never listed: the id
    });

    test('a later call replaces the cache; sparse JSON falls back to the id', () async {
      StoreInfo.remember([const StoreInfo(id: 'old', name: 'Old Shop')]);
      expect(StoreInfo.nameFor('old'), 'Old Shop');
      final api = _api([], (_) => [{'id': 'kith'}, {'name': 'no id'}]);
      final stores = await api.stores();
      expect(stores.length, 2);
      expect(stores.first.name, 'kith'); // name missing -> id
      expect(stores.first.count, 0);
      expect(stores.first.departments, isEmpty);
      expect(StoreInfo.nameFor('old'), 'old'); // replaced, not merged
      expect(StoreInfo.nameFor('kith'), 'kith');
    });

    test('an old server answering with an object (not a list) yields an empty list', () async {
      final api = _api([], (_) => {'detail': 'nope'});
      expect(await api.stores(), isEmpty);
    });
  });
}
