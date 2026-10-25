import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/features/social/optimistic_like.dart';
import 'package:dress_to_impress/features/social/inspo_bindings.dart';
import 'package:dress_to_impress/features/social/social_feed.dart';
import 'package:dress_to_impress/features/social/comments_sheet.dart';
import 'package:dress_to_impress/features/shared/natural_photo_frame.dart';

Future<void> tick() => Future<void>.delayed(Duration.zero);
LikeResult result(bool liked, int count) =>
    LikeResult(postId: 'p', liked: liked, likeCount: count);
FitCheckComment comment(String id) => FitCheckComment(
    id: id,
    userId: 'u$id',
    text: 'Comment $id',
    createdAt: '2026-10-24T12:0$id:00Z');
Api noHttp() => Api(
    client: MockClient(
        (r) async => throw StateError('Unexpected request ${r.url.path}')));
Future<void> mount(WidgetTester t, Widget child) async {
  t.view.physicalSize = const Size(430, 900);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  await t.pumpAndSettle();
}

void main() {
  testWidgets(
      'overlapping newest-page load and send deduplicate and keep total accurate',
      (t) async {
    final firstPage = Completer<CommentsPageData>();
    final posted = Completer<http.Response>();
    final totals = <int>[];
    var loads = 0;
    final client = Api(client: MockClient((r) => posted.future));
    t.view.physicalSize = const Size(430, 900);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: CommentsSheet(
                api: client,
                postId: 'p',
                initial: [],
                onAdded: (_) {},
                onTotal: totals.add,
                loadPage: (before) {
                  loads++;
                  return loads == 1
                      ? firstPage.future
                      : Future.value((
                          comments: [comment('1'), comment('2')],
                          total: 5,
                          nextBefore: null
                        ));
                }))));
    await t.pump();
    await t.enterText(
        find.widgetWithText(TextField, 'Add a comment…'), 'Comment 5');
    await t.tap(find.byTooltip('Send comment'));
    await t.pump();
    firstPage.complete((comments: [comment('5')], total: 5, nextBefore: '5'));
    await t.pump();
    await t.pump();
    posted.complete(http.Response(
        jsonEncode({
          'id': '5',
          'user_id': 'u5',
          'text': 'Comment 5',
          'created_at': '2026-10-24T12:05:00Z',
          'comment_count': 5
        }),
        200));
    await t.pumpAndSettle();
    expect(find.text('Comment 5'), findsOneWidget);
    await t.tap(find.text('Load older comments'));
    await t.pumpAndSettle();
    expect(totals, [5, 5]);
  });

  test(
      'like flips immediately and serializes a reversal behind the first write',
      () async {
    final a = Completer<LikeResult>(), b = Completer<LikeResult>();
    final calls = <bool>[];
    final state = OptimisticLike(
        liked: false,
        count: 10,
        write: (liked) {
          calls.add(liked);
          return calls.length == 1 ? a.future : b.future;
        });
    addTearDown(state.dispose);
    state.toggle();
    expect((state.liked, state.count), (true, 11));
    state.toggle();
    expect((state.liked, state.count), (false, 10));
    expect(calls, [true]);
    a.complete(result(true, 11));
    await tick();
    expect(calls, [true, false]);
    expect((state.liked, state.count), (false, 10));
    b.complete(result(false, 10));
    await tick();
    expect(state.saving, false);
  });
  test('rapid taps coalesce to the latest intent without double toggles',
      () async {
    final done = Completer<LikeResult>();
    final calls = <bool>[];
    final state = OptimisticLike(
        liked: false,
        count: 0,
        write: (v) {
          calls.add(v);
          return done.future;
        });
    addTearDown(state.dispose);
    state.toggle();
    state.toggle();
    state.toggle();
    done.complete(result(true, 1));
    await tick();
    expect(calls, [true]);
    expect((state.liked, state.count), (true, 1));
  });
  test('latest failed like rolls back and does not retry itself', () async {
    final done = Completer<LikeResult>();
    var calls = 0;
    final state = OptimisticLike(
        liked: false,
        count: 4,
        write: (v) {
          calls++;
          return done.future;
        });
    addTearDown(state.dispose);
    state.toggle();
    done.completeError(StateError('offline'));
    await tick();
    expect((state.liked, state.count), (false, 4));
    expect(state.error, isNotNull);
    expect(calls, 1);
    expect(state.saving, false);
  });
  test('failed earlier write still reconciles a newer unlike intent', () async {
    final first = Completer<LikeResult>();
    final calls = <bool>[];
    final state = OptimisticLike(
        liked: false,
        count: 4,
        write: (v) {
          calls.add(v);
          return calls.length == 1
              ? first.future
              : Future.value(result(false, 4));
        });
    addTearDown(state.dispose);
    state.toggle();
    state.toggle();
    first.completeError(StateError('ambiguous timeout'));
    await tick();
    await tick();
    expect(calls, [true, false]);
    expect((state.liked, state.count), (false, 4));
    expect(state.error, isNull);
  });
  testWidgets(
      'post reflects explicit-state like before the response and rolls back on error',
      (t) async {
    final pending = Completer<LikeResult>();
    final calls = <bool>[];
    await mount(
        t,
        SingleChildScrollView(
            child: FitPostCard(
                post: const FitCheckPost(
                    id: 'p',
                    userId: 'other',
                    photoUrl: '',
                    likeCount: 0,
                    likedByMe: false),
                api: noHttp(),
                onShop: (_) {},
                bindings: InspoBindings(setLike: (id, liked) {
                  expect(id, 'p');
                  calls.add(liked);
                  return pending.future;
                }))));
    await t.ensureVisible(find.byKey(const ValueKey('like-p')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('like-p')));
    await t.pump();
    expect(
        find.descendant(
            of: find.byKey(const ValueKey('like-p')), matching: find.text('1')),
        findsOneWidget);
    expect(find.byIcon(Icons.favorite), findsOneWidget);
    pending.completeError(StateError('offline'));
    await t.pumpAndSettle();
    expect(find.byIcon(Icons.favorite_border), findsOneWidget);
    expect(calls, [true]);
    expect(
        find.text('Could not update like. Please try again.'), findsOneWidget);
  });
  testWidgets(
      'comments load newest page then older cursor with names and no duplicates',
      (t) async {
    final cursors = <String?>[];
    await mount(
        t,
        CommentsSheet(
            api: noHttp(),
            postId: 'p',
            initial: [comment('3'), comment('4')],
            onAdded: (_) {},
            authorLabel: (c) => 'Person ${c.id}',
            loadPage: (before) async {
              cursors.add(before);
              return before == null
                  ? (
                      comments: [comment('3'), comment('4')],
                      total: 4,
                      nextBefore: '3'
                    )
                  : (
                      comments: [comment('1'), comment('2'), comment('3')],
                      total: 4,
                      nextBefore: null
                    );
            }));
    expect(find.text('Person 4'), findsOneWidget);
    await t.tap(find.text('Load older comments'));
    await t.pumpAndSettle();
    expect(cursors, [null, '3']);
    expect(find.text('Comment 3'), findsOneWidget);
    expect(find.text('Person 1'), findsOneWidget);
    expect(find.text('Load older comments'), findsNothing);
    expect(t.getTopLeft(find.text('Comment 1')).dy,
        lessThan(t.getTopLeft(find.text('Comment 4')).dy));
  });
  testWidgets('older page failure keeps draft and retries the same cursor',
      (t) async {
    final cursors = <String?>[];
    var failed = false;
    await mount(
        t,
        CommentsSheet(
            api: noHttp(),
            postId: 'p',
            initial: [],
            onAdded: (_) {},
            loadPage: (before) async {
              cursors.add(before);
              if (before == null) {
                return (comments: [comment('3')], total: 3, nextBefore: '3');
              }
              if (!failed) {
                failed = true;
                throw StateError('offline');
              }
              return (
                comments: [comment('1'), comment('2')],
                total: 3,
                nextBefore: null
              );
            }));
    await t.enterText(
        find.widgetWithText(TextField, 'Add a comment…'), 'Keep my draft');
    await t.tap(find.text('Load older comments'));
    await t.pumpAndSettle();
    expect(find.text('Comment 3'), findsOneWidget);
    await t.tap(find.text('Could not load comments. Retry'));
    await t.pumpAndSettle();
    expect(cursors, [null, '3', '3']);
    expect(t.widget<TextField>(find.byType(TextField)).controller!.text,
        'Keep my draft');
  });
  testWidgets(
      'server photo dimensions establish capped geometry before image loads',
      (t) async {
    await mount(
        t,
        const NaturalPhotoFrame(
            url: '', width: 500, height: 2500, child: SizedBox()));
    expect(t.widget<AspectRatio>(find.byType(AspectRatio)).aspectRatio, 9 / 16);
  });
}
