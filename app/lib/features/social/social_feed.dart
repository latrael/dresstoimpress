import 'dart:math' as math;
import '../shared/niche_theme.dart';
import '../shared/niche_photo.dart';
import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../store/store_controller.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';
import '../closet/closet_screen.dart';
import '../store/cart_screen.dart';
import '../shared/natural_photo_frame.dart';
import 'comments_sheet.dart';
import 'inspo_bindings.dart';
import '../profile/friends_card.dart';

class SocialFeed extends StatefulWidget {
  const SocialFeed(
      {super.key,
      required this.store,
      required this.onShop,
      this.picker = pickPhoto,
      this.onTagSearch,
      this.authorId,
      this.bindings});
  final StoreController store;
  final void Function(List<RankedProduct>) onShop;
  final PhotoPicker picker;
  final void Function(String)? onTagSearch;
  final String? authorId;
  final InspoBindings? bindings;
  @override
  State<SocialFeed> createState() => _SocialFeedState();
}

/// Inspo scope: posts by friends (+ mine) or by everyone.
enum InspoScope { friends, everyone }

class _SocialFeedState extends State<SocialFeed> {
  /// Everyone by default: the Friends tab is only different once you've added friends.
  InspoScope scope = InspoScope.everyone;
  Set<String> friendIds = {};
  late Future<List<FitCheckPost>> posts = load();

  Future<List<FitCheckPost>> load() async {
    if (widget.store.demo) return [];
    final api = widget.store.api;
    if (widget.authorId == null && scope == InspoScope.friends) {
      try {
        friendIds = (await api.friends()).map((f) => f.id).toSet();
      } catch (_) {
        friendIds = {};
      }
      if (friendIds.isEmpty) return [];
    }
    // The server scopes the feed (friends' + own posts; friends-only posts stay in their circle).
    return api.fitCheckFeed(
        limit: 100,
        author: widget.authorId,
        scope: widget.authorId == null && scope == InspoScope.friends ? 'friends' : null);
  }

  void setScope(InspoScope s) {
    if (s == scope) return;
    setState(() {
      scope = s;
      posts = load();
    });
  }

  Widget scopeToggle(BuildContext context) {
    final t = Niche.of(context);
    Widget seg(InspoScope s, String label) {
      final on = scope == s;
      return Expanded(
          child: GestureDetector(
              onTap: () => setScope(s),
              child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOut,
                  padding: const EdgeInsets.symmetric(vertical: 7),
                  decoration: BoxDecoration(
                      color: on ? t.brand : Colors.transparent,
                      borderRadius: BorderRadius.circular(20)),
                  child: Text(label,
                      textAlign: TextAlign.center,
                      style: Niche.ui(13, 18, FontWeight.w600, on ? t.cream : t.muted)))));
    }

    return Semantics(
        label: 'Inspo scope',
        child: NicheGlass(
            radius: 22,
            opacity: .55,
            blur: 12,
            child: Padding(
                padding: const EdgeInsets.all(3),
                child: Row(children: [
                  seg(InspoScope.friends, 'Friends'),
                  seg(InspoScope.everyone, 'Everyone'),
                ]))));
  }
  void refresh() => setState(() {
        posts = load();
      });

  Future<void> addFriends() async {
    await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        // the sheet's own context: it rebuilds when the keyboard opens, so the search box stays above it
        builder: (sheet) => Padding(
            padding: EdgeInsets.fromLTRB(
                16, 16, 16, 16 + MediaQuery.viewInsetsOf(sheet).bottom),
            child: SingleChildScrollView(
                child: FriendsCard(api: widget.store.api))));
    refresh();
  }
  Future<void> create() async {
    final posted = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
            builder: (_) => CreateFitCheckScreen(
                api: widget.store.api, picker: widget.picker)));
    if (posted == true && mounted) refresh();
  }

  @override
  Widget build(BuildContext context) => Column(children: [
        // One row: scope toggle · add friends · OOTD +. Pull down to refresh; no reload button.
        if (!widget.store.demo)
          Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: Row(children: [
                Expanded(
                    child: widget.authorId == null
                        ? scopeToggle(context)
                        : Text('Their fits',
                            style: Niche.ui(
                                14, 20, FontWeight.w600, Niche.of(context).muted))),
                if (widget.authorId == null) ...[
                  const SizedBox(width: 12),
                  _HeaderIcon(
                      tooltip: 'Add friends',
                      icon: NicheIcons.personOutline,
                      onTap: addFriends),
                ],
                const SizedBox(width: 12),
                _OotdButton(onTap: create),
              ])),
        Expanded(
            child: FutureBuilder<List<FitCheckPost>>(
                future: posts,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return Center(
                        child: TextButton(
                            onPressed: refresh,
                            child: const Text('Could not load fits. Retry')));
                  }
                  if (!snapshot.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.data!.isEmpty) {
                    if (!widget.store.demo &&
                        widget.authorId == null &&
                        scope == InspoScope.friends) {
                      final t = Niche.of(context);
                      return Center(
                          child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Text(
                            friendIds.isEmpty
                                ? 'No friends yet'
                                : 'No fits from friends yet',
                            style: Niche.ui(16, 22, FontWeight.w600, t.ink)),
                        const SizedBox(height: 6),
                        Text('Add friends by @handle or friend code.',
                            style: Niche.ui(13, 18, FontWeight.w500, t.muted)),
                        const SizedBox(height: 14),
                        FilledButton.icon(
                            onPressed: addFriends,
                            icon: const Icon(NicheIcons.personOutline),
                            label: const Text('Add friends')),
                      ]));
                    }
                    return Center(
                        child: Text(widget.store.demo
                            ? 'Connect to explore Inspo.'
                            : 'No fits yet. Your next look could be the first.'));
                  }
                  return RefreshIndicator(
                      onRefresh: () async {
                        refresh();
                        await posts.catchError((_) => <FitCheckPost>[]);
                      },
                      child: ListView(
                          padding: EdgeInsets.fromLTRB(
                              16, 12, 16, Niche.bottomSpace(context)),
                          children: [
                            for (final post in snapshot.data!)
                              FitPostCard(
                                  key: ValueKey(post.id),
                                  post: post,
                                  bindings: widget.bindings ??
                                      InspoBindings.fromApi(widget.store.api),
                                  api: widget.store.api,
                                  onShop: widget.onShop,
                                  onTagSearch: widget.onTagSearch,
                                  onDeleted: refresh,
                                  onAuthor: (id, name) => Navigator.push<void>(
                                      context,
                                      MaterialPageRoute(
                                          builder: (_) => FeaturePage(
                                              title: name,
                                              child: SocialFeed(
                                                  store: widget.store,
                                                  onShop: widget.onShop,
                                                  onTagSearch:
                                                      widget.onTagSearch,
                                                  authorId: id,
                                                  bindings: widget.bindings)))))
                          ]));
                })),
      ]);
}

/// Round glass icon button that matches the scope toggle's height (36).
class _HeaderIcon extends StatelessWidget {
  const _HeaderIcon(
      {required this.tooltip, required this.icon, required this.onTap});
  final String tooltip;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    return Tooltip(
        message: tooltip,
        child: Semantics(
            button: true,
            label: tooltip,
            child: GestureDetector(
                onTap: () {
                  HapticFeedback.selectionClick();
                  onTap();
                },
                child: NicheGlass(
                    radius: 18,
                    opacity: .55,
                    blur: 12,
                    child: SizedBox(
                        width: 36,
                        height: 36,
                        child: Icon(icon, size: 18, color: t.ink))))));
  }
}

/// "OOTD +": post today's outfit. A merlot pill, same height as the toggle.
class _OotdButton extends StatelessWidget {
  const _OotdButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    return Tooltip(
        message: 'Post your OOTD',
        child: Semantics(
            button: true,
            label: 'Post your OOTD',
            child: GestureDetector(
                onTap: () {
                  HapticFeedback.lightImpact();
                  onTap();
                },
                child: Container(
                    height: 36,
                    padding: const EdgeInsets.fromLTRB(14, 0, 10, 0),
                    decoration: BoxDecoration(
                        color: t.brand,
                        borderRadius: BorderRadius.circular(18),
                        boxShadow: [
                          BoxShadow(
                              color: t.brand.withValues(alpha: .25),
                              blurRadius: 12,
                              offset: const Offset(0, 4))
                        ]),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Text('OOTD',
                          style: Niche.ui(13, 18, FontWeight.w700, t.cream)),
                      const SizedBox(width: 4),
                      Icon(NicheIcons.add, size: 18, color: t.cream),
                    ])))));
  }
}

class CreateFitCheckScreen extends StatefulWidget {
  const CreateFitCheckScreen(
      {super.key, required this.api, this.picker = pickPhoto});
  final Api api;
  final PhotoPicker picker;
  @override
  State<CreateFitCheckScreen> createState() => _CreateFitCheckScreenState();
}

class _CreateFitCheckScreenState extends State<CreateFitCheckScreen> {
  PickedPhoto? photo;
  final caption = TextEditingController();
  String? error;
  bool busy = false;
  /// Who sees this fit: 'public' (Everyone) or 'friends'.
  String visibility = 'public';
  @override
  void dispose() {
    caption.dispose();
    super.dispose();
  }

  Future<void> choose() async {
    try {
      final selected = await widget.picker();
      if (mounted && selected != null) {
        setState(() {
          photo = selected;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    }
  }

  Future<void> post() async {
    if (photo == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.createFitCheckUpload(photo!.bytes,
          mimeType: photo!.mimeType,
          caption: caption.text.trim(),
          visibility: visibility);
      if (mounted) Navigator.pop(context, true);
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Could not post this fit. Check your connection before trying again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your OOTD',
      child: ListView(padding: const EdgeInsets.all(24), children: [
        const Text(
            'Share an outfit in Inspo. Your photo and caption are uploaded to your connected server; the outfit is tagged automatically.'),
        const SizedBox(height: 16),
        if (photo != null)
          SizedBox(
              height: 280,
              child: Image.memory(Uint8List.fromList(photo!.bytes),
                  fit: BoxFit.contain)),
        OutlinedButton(
            onPressed: busy ? null : choose,
            child: const Text('Choose outfit photo')),
        const SizedBox(height: 16),
        TextField(
            controller: caption,
            enabled: !busy,
            maxLines: 3,
            maxLength: 280,
            decoration: const InputDecoration(labelText: 'Caption')),
        const SizedBox(height: 16),
        Semantics(
            label: 'Who can see this fit',
            child: SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'friends', label: Text('Friends')),
                  ButtonSegment(value: 'public', label: Text('Everyone')),
                ],
                selected: {visibility},
                showSelectedIcon: false,
                onSelectionChanged: busy
                    ? null
                    : (v) => setState(() => visibility = v.first))),
        const SizedBox(height: 16),
        FilledButton(
            onPressed: busy || photo == null ? null : post,
            child: Text(busy ? 'Posting and tagging…' : 'Post to Inspo')),
        if (error != null) Text(error!),
      ]));
}

class FitPostCard extends StatefulWidget {
  const FitPostCard(
      {super.key,
      required this.post,
      required this.api,
      required this.onShop,
      this.onTagSearch,
      this.onAuthor,
      this.onDeleted,
      this.bindings});
  final FitCheckPost post;
  final Api api;
  final void Function(List<RankedProduct>) onShop;
  final void Function(String)? onTagSearch;
  final void Function(String id, String name)? onAuthor;
  final VoidCallback? onDeleted;
  final InspoBindings? bindings;
  @override
  State<FitPostCard> createState() => _FitPostCardState();
}

/// One Inspo post: photo with "Similar" top-right, emoji reactions bottom-left, comments next to them.
/// Fit Score lives on your own outfits in Closet, not on other people's posts.
class _FitPostCardState extends State<FitPostCard>
    with SingleTickerProviderStateMixin {
  late final burst = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 650));
  late FitCheckPost post = widget.post;
  late Map<String, int> reactions = _initialReactions(post);
  late String? mine = _initialMine(post);
  String burstEmoji = fitCheckReactions.first;
  late List<FitCheckComment> comments = [...post.comments];
  late int commentCount = post.commentCount ?? comments.length;
  String? busy;
  String? error;
  bool showTags = false;
  bool picking = false;
  int reactSeq = 0;
  InspoBindings get bindings =>
      widget.bindings ?? InspoBindings.fromApi(widget.api);

  static Map<String, int> _initialReactions(FitCheckPost p) {
    if (p.reactions.isNotEmpty) return {...p.reactions};
    final likes = p.likeCount ?? p.likes.length;
    return likes > 0 ? {'😍': likes} : {};
  }

  static String? _initialMine(FitCheckPost p) =>
      p.myReaction ?? ((p.likedByMe ?? false) ? '😍' : null);

  int get total => reactions.values.fold(0, (a, b) => a + b);

  @override
  void didUpdateWidget(covariant FitPostCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.post, widget.post)) {
      post = widget.post;
      reactions = _initialReactions(post);
      mine = _initialMine(post);
      comments = [...post.comments];
      commentCount = post.commentCount ?? comments.length;
    }
  }

  @override
  void dispose() {
    burst.dispose();
    super.dispose();
  }

  Future<void> action(String name, Future<void> Function() task) async {
    if (busy != null) return;
    setState(() {
      busy = name;
      error = null;
    });
    try {
      await task();
    } catch (_) {
      if (mounted) setState(() => error = 'Could not $name. Please try again.');
    } finally {
      if (mounted) setState(() => busy = null);
    }
  }

  /// Optimistic: the count changes on tap; a failure puts the old state back.
  Future<void> react(String? emoji) async {
    Niche.select();
    final before = (Map<String, int>.from(reactions), mine);
    setState(() {
      picking = false;
      error = null;
      if (mine != null) {
        final left = (reactions[mine!] ?? 1) - 1;
        if (left <= 0) {
          reactions.remove(mine);
        } else {
          reactions[mine!] = left;
        }
      }
      if (emoji != null) reactions[emoji] = (reactions[emoji] ?? 0) + 1;
      mine = emoji;
      if (emoji != null) burstEmoji = emoji;
    });
    if (emoji != null && !Niche.reduced(context)) burst.forward(from: 0);
    final seq = ++reactSeq;
    try {
      if (bindings.setReaction != null) {
        final r = await bindings.setReaction!(post.id, emoji);
        if (mounted && seq == reactSeq) {
          setState(() {
            reactions = {...r.reactions};
            mine = r.myReaction;
          });
        }
      } else if (bindings.setLike != null) {
        await bindings.setLike!(post.id, emoji != null);
      } else {
        await widget.api.setFitCheckReaction(post.id, emoji);
      }
    } catch (_) {
      if (mounted && seq == reactSeq) {
        setState(() {
          reactions = before.$1;
          mine = before.$2;
          error = 'Could not update your reaction. Please try again.';
        });
      }
    }
  }

  Future<void> deletePost() async {
    final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Delete this post?'),
                content: const Text(
                    'Remove your outfit and its comments from Inspo?'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Keep')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Delete'))
                ]));
    if (yes != true || !mounted) return;
    await action('delete post', () async {
      await widget.api.deleteFitCheck(post.id);
      widget.onDeleted?.call();
    });
  }

  Future<void> openComments() => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      sheetAnimationStyle: AnimationStyle(
          duration: Niche.reduced(context)
              ? const Duration(milliseconds: 120)
              : const Duration(milliseconds: 300),
          reverseDuration: const Duration(milliseconds: 280)),
      builder: (_) => CommentsSheet(
          api: widget.api,
          postId: post.id,
          initial: comments,
          loadPage: bindings.commentsForPost?.call(post.id),
          authorLabel: bindings.commentAuthor,
          onTotal: (total) {
            if (mounted) setState(() => commentCount = total);
          },
          onAdded: (added) {
            if (mounted) {
              setState(() {
                final isNew = !comments.any((c) => c.id == added.id);
                if (isNew) comments.add(added);
                final total =
                    added.commentCount ?? commentCount + (isNew ? 1 : 0);
                if (total > commentCount) commentCount = total;
              });
            }
          }));

  Future<void> openSimilar() => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) =>
          FindSimilarSheet(api: widget.api, post: post, onShop: widget.onShop));

  Future<void> editTags() async {
    final result = await showDialog<List<FitTag>>(
        context: context, builder: (_) => EditTagsDialog(tags: post.tagged));
    if (result == null || !mounted) return;
    await action('save tags', () async {
      final updated = await widget.api.updateFitCheckTags(post.id, result);
      if (mounted) setState(() => post = updated);
    });
  }

  String get author => post.authorName ?? post.userId;
  bool get isMine => post.userId == widget.api.settings.userId;

  Widget avatar(BuildContext context) {
    final t = Niche.of(context);
    return CircleAvatar(
        radius: 18,
        backgroundColor: t.blush,
        child: Text(author.isEmpty ? '?' : author[0].toUpperCase(),
            style: Niche.display(16, 20, t.brand)));
  }

  /// A solid tonal pill for actions on the page (glass is only legible over a photo).
  Widget actionPill(BuildContext context,
      {required Widget child,
      required VoidCallback? onTap,
      VoidCallback? onLongPress,
      Key? key,
      String? tooltip}) {
    final t = Niche.of(context);
    return NichePress(
        child: Material(
            color: t.isDark ? t.blush : t.stone,
            borderRadius: BorderRadius.circular(999),
            child: InkWell(
                key: key,
                onTap: onTap,
                onLongPress: onLongPress,
                borderRadius: BorderRadius.circular(999),
                child: Tooltip(
                    message: tooltip ?? '',
                    child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 9),
                        child: child)))));
  }

  Widget glassPill(BuildContext context,
          {required Widget child,
          required VoidCallback? onTap,
          VoidCallback? onLongPress,
          Key? key,
          String? tooltip}) =>
      NichePress(
          child: NicheGlass(
              radius: 999,
              opacity: .78,
              child: Material(
                  type: MaterialType.transparency,
                  child: InkWell(
                      key: key,
                      onTap: onTap,
                      onLongPress: onLongPress,
                      borderRadius: BorderRadius.circular(999),
                      child: Tooltip(
                          message: tooltip ?? '',
                          child: Padding(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 14, vertical: 9),
                              child: child))))));

  Widget reactionRow(BuildContext context) {
    final t = Niche.of(context);
    final top = (reactions.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value)))
        .take(3)
        .map((e) => e.key)
        .join();
    return Row(children: [
      Semantics(
          button: true,
          label: mine == null ? 'React to this fit' : 'Your reaction $mine',
          child: actionPill(context,
              key: ValueKey('react-${post.id}'),
              tooltip: 'React',
              onTap: () => setState(() => picking = !picking),
              onLongPress: () =>
                  react(mine == null ? fitCheckReactions.first : null),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Opacity(
                    opacity: mine == null ? .45 : 1,
                    child: Text(mine ?? fitCheckReactions.first,
                        style: const TextStyle(fontSize: 18))),
                if (total > 0) ...[
                  const SizedBox(width: 8),
                  Text('$total',
                      style: Niche.ui(14, 18, FontWeight.w700, t.ink)),
                ],
              ]))),
      if (top.isNotEmpty && total > 1) ...[
        const SizedBox(width: 8),
        Text(top, style: const TextStyle(fontSize: 14)),
      ],
      const SizedBox(width: 10),
      actionPill(context,
          key: ValueKey('comments-${post.id}'),
          tooltip: 'Comments',
          onTap: openComments,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(NicheIcons.chatBubbleOutline, size: 18, color: t.ink),
            const SizedBox(width: 8),
            Text('$commentCount',
                style: Niche.ui(14, 18, FontWeight.w700, t.ink)),
          ])),
    ]);
  }

  Widget picker(BuildContext context) => AnimatedSize(
      duration: Niche.duration,
      curve: Curves.easeOutCubic,
      alignment: Alignment.topLeft,
      child: !picking
          ? const SizedBox(width: double.infinity)
          : Padding(
              padding: const EdgeInsets.only(top: 10),
              child: DecoratedBox(
                  decoration: BoxDecoration(
                      color: Niche.of(context).isDark
                          ? Niche.of(context).blush
                          : Niche.of(context).stone,
                      borderRadius: BorderRadius.circular(999)),
                  child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 4),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        for (final e in fitCheckReactions)
                          Semantics(
                              button: true,
                              selected: mine == e,
                              label: 'React $e',
                              child: InkWell(
                                  key: ValueKey('react-${post.id}-$e'),
                                  borderRadius: BorderRadius.circular(999),
                                  onTap: () => react(mine == e ? null : e),
                                  child: AnimatedContainer(
                                      duration: Niche.duration,
                                      padding: const EdgeInsets.all(8),
                                      decoration: BoxDecoration(
                                          shape: BoxShape.circle,
                                          color: mine == e
                                              ? Niche.of(context)
                                                  .brand
                                                  .withValues(alpha: .22)
                                              : Colors.transparent),
                                      child: Text(e,
                                          style: TextStyle(
                                              fontSize:
                                                  mine == e ? 26 : 24))))),
                      ])))));

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    final textTheme = Theme.of(context).textTheme;
    return Padding(
        padding: const EdgeInsets.only(bottom: 36),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(children: [
                InkWell(
                    borderRadius: BorderRadius.circular(999),
                    onTap: widget.onAuthor == null
                        ? null
                        : () => widget.onAuthor!(post.userId, author),
                    child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(children: [
                          avatar(context),
                          const SizedBox(width: 10),
                          Text(author, style: textTheme.titleMedium),
                        ]))),
                const Spacer(),
                if (isMine)
                  PopupMenuButton<String>(
                      tooltip: 'Post options',
                      enabled: busy == null,
                      onSelected: (v) =>
                          v == 'tags' ? editTags() : deletePost(),
                      itemBuilder: (_) => const [
                            PopupMenuItem(
                                value: 'tags', child: Text('Edit tags')),
                            PopupMenuItem(
                                value: 'delete', child: Text('Delete post')),
                          ],
                      icon: Text('•••',
                          style: Niche.ui(14, 18, FontWeight.w800, t.muted)
                              .copyWith(letterSpacing: 1.5))),
              ])),
          NaturalPhotoFrame(
              url: widget.api.imageProxyUrl(post.photoUrl),
              width: bindings.photoSize?.call(post)?.width,
              height: bindings.photoSize?.call(post)?.height,
              child: Semantics(
                  container: true,
                  explicitChildNodes: true,
                  button: true,
                  label: showTags ? 'Hide outfit tags' : 'Show outfit tags',
                  child: GestureDetector(
                      onTap: () => setState(() => showTags = !showTags),
                      child: Stack(fit: StackFit.expand, children: [
                        ClipRRect(
                            borderRadius: BorderRadius.circular(Niche.radius),
                            child: NichePhoto(
                                url: widget.api.imageProxyUrl(post.photoUrl),
                                label: 'Outfit by $author')),
                        IgnorePointer(
                            child: AnimatedBuilder(
                                animation: burst,
                                builder: (context, _) => !burst.isAnimating
                                    ? const SizedBox.shrink()
                                    : Center(
                                        child: Opacity(
                                            opacity:
                                                math.sin(burst.value * math.pi),
                                            child: Transform.scale(
                                                scale: .7 + burst.value * .6,
                                                child: Text(burstEmoji,
                                                    style: const TextStyle(
                                                        fontSize: 84))))))),
                        Positioned(
                            top: 12,
                            right: 12,
                            child: Semantics(
                                button: true,
                                label: 'Find similar look',
                                child: glassPill(context,
                                    key: ValueKey('similar-${post.id}'),
                                    tooltip: 'Find similar look',
                                    onTap: post.tagged.isEmpty
                                        ? null
                                        : openSimilar,
                                    child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(NicheIcons.autoAwesome,
                                              size: 16, color: t.brand),
                                          const SizedBox(width: 6),
                                          Text('Similar',
                                              style: Niche.ui(13, 16,
                                                  FontWeight.w700, t.ink)),
                                        ])))),
                        Positioned(
                            left: 12,
                            bottom: 12,
                            right: 12,
                            child: showTags
                                ? NicheGlass(
                                    radius: 22,
                                    opacity: .85,
                                    child: Container(
                                        padding: const EdgeInsets.all(10),
                                        constraints: const BoxConstraints(
                                            maxHeight: 180),
                                        child: SingleChildScrollView(
                                            child: Wrap(
                                                spacing: 6,
                                                runSpacing: 6,
                                                children: [
                                              for (final tag in post.tagged)
                                                CatalogTag(
                                                    api: widget.api,
                                                    tag: tag,
                                                    onProduct: (p) => widget
                                                            .onShop([
                                                          RankedProduct(
                                                              product: p)
                                                        ]),
                                                    onSearch:
                                                        widget.onTagSearch)
                                            ]))))
                                : Align(
                                    alignment: Alignment.bottomLeft,
                                    child: post.tagged.isEmpty
                                        ? const SizedBox.shrink()
                                        : NicheGlass(
                                            radius: 999,
                                            opacity: .7,
                                            child: Padding(
                                                padding:
                                                    const EdgeInsets.all(8),
                                                child: Icon(
                                                    NicheIcons
                                                        .localOfferOutlined,
                                                    size: 16,
                                                    color: t.ink))))),
                      ])))),
          const SizedBox(height: 12),
          reactionRow(context),
          picker(context),
          if (post.caption?.isNotEmpty == true)
            Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text.rich(TextSpan(children: [
                  TextSpan(
                      text: '$author  ',
                      style: Niche.ui(14, 20, FontWeight.w700, t.ink)),
                  TextSpan(
                      text: post.caption!,
                      style: Niche.ui(14, 20, FontWeight.w400, t.ink)),
                ]))),
          if (commentCount > 0)
            Padding(
                padding: const EdgeInsets.only(top: 6),
                child: InkWell(
                    onTap: openComments,
                    child: Text(
                        commentCount == 1
                            ? 'View 1 comment'
                            : 'View all $commentCount comments',
                        style: Niche.ui(13, 18, FontWeight.w500, t.muted)))),
          if (busy != null)
            const Padding(
                padding: EdgeInsets.only(top: 10),
                child: LinearProgressIndicator()),
          if (error != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error))),
        ]));
  }
}

/// "Find similar look": one expandable section per tagged piece; what you already own first, then
/// pieces to shop. Tapping a product opens it (size + add to cart).
class FindSimilarSheet extends StatefulWidget {
  const FindSimilarSheet(
      {super.key, required this.api, this.post, this.load, required this.onShop})
      : assert(post != null || load != null);
  final Api api;
  final FitCheckPost? post;

  /// Where the groups come from when it isn't an Inspo post (a Discover pin: `api.pinSimilar`).
  final Future<List<SimilarLookGroup>> Function()? load;
  final void Function(List<RankedProduct>) onShop;
  @override
  State<FindSimilarSheet> createState() => _FindSimilarSheetState();
}

class _FindSimilarSheetState extends State<FindSimilarSheet> {
  Future<List<SimilarLookGroup>> fetch() =>
      widget.load?.call() ?? widget.api.similarLook(widget.post!.id);
  late Future<List<SimilarLookGroup>> groups = fetch();

  void shop(List<RankedProduct> products) {
    if (products.isEmpty) return;
    Navigator.pop(context);
    widget.onShop(products);
  }

  static String _title(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

  Widget label(BuildContext context, String text) => Padding(
      padding: const EdgeInsets.fromLTRB(4, 8, 4, 8),
      child: Text(text.toUpperCase(),
          style: Niche.ui(11, 14, FontWeight.w700, Niche.of(context).muted)
              .copyWith(letterSpacing: 1.1)));

  Widget tile(BuildContext context,
      {required String url,
      required String title,
      String? subtitle,
      required VoidCallback onTap,
      Key? key}) {
    final t = Niche.of(context);
    return SizedBox(
        width: 124,
        child: NichePress(
            child: InkWell(
                key: key,
                onTap: onTap,
                borderRadius: BorderRadius.circular(20),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AspectRatio(
                          aspectRatio: 3 / 4,
                          child: ClipRRect(
                              borderRadius: BorderRadius.circular(20),
                              child: ColoredBox(
                                  color: t.stone,
                                  child: url.isEmpty
                                      ? Icon(NicheIcons.checkroomOutlined,
                                          color: t.muted)
                                      : NichePhoto(url: url, label: title)))),
                      const SizedBox(height: 6),
                      Text(title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Niche.ui(12, 16, FontWeight.w600, t.ink)),
                      if (subtitle != null)
                        Text(subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Niche.ui(11, 14, FontWeight.w500, t.muted)),
                    ]))));
  }

  Widget row(List<Widget> children) => SizedBox(
      height: 214,
      child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 4),
          itemCount: children.length,
          separatorBuilder: (_, __) => const SizedBox(width: 12),
          itemBuilder: (_, i) => children[i]));

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    return DraggableScrollableSheet(
        expand: false,
        initialChildSize: .78,
        minChildSize: .4,
        maxChildSize: .95,
        builder: (context, scroll) => FutureBuilder<List<SimilarLookGroup>>(
            future: groups,
            builder: (context, snap) {
              final header = Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Find similar look',
                            style: Niche.display(26, 32, t.brand)),
                        const SizedBox(height: 4),
                        Text('What you already own first, then pieces to shop.',
                            style: Niche.ui(14, 20, FontWeight.w500, t.muted)),
                      ]));
              if (snap.hasError) {
                return ListView(controller: scroll, children: [
                  header,
                  Padding(
                      padding: const EdgeInsets.all(20),
                      child: TextButton(
                          onPressed: () => setState(() {
                                groups = fetch();
                              }),
                          child: const Text(
                              'Could not load similar pieces. Retry'))),
                ]);
              }
              if (!snap.hasData) {
                return ListView(controller: scroll, children: [
                  header,
                  const Padding(
                      padding: EdgeInsets.all(40),
                      child: Center(child: CircularProgressIndicator())),
                ]);
              }
              final data = snap.data!;
              final all = [for (final g in data) ...g.products];
              return ListView(
                  controller: scroll,
                  padding: EdgeInsets.only(
                      bottom: 24 + MediaQuery.paddingOf(context).bottom),
                  children: [
                    header,
                    if (data.isEmpty)
                      const Padding(
                          padding: EdgeInsets.all(20),
                          child: Text('No tagged pieces on this fit yet.')),
                    for (var i = 0; i < data.length; i++)
                      Theme(
                          data: Theme.of(context)
                              .copyWith(dividerColor: Colors.transparent),
                          child: ExpansionTile(
                              key: ValueKey('similar-group-$i'),
                              initiallyExpanded: i == 0,
                              tilePadding:
                                  const EdgeInsets.symmetric(horizontal: 20),
                              childrenPadding:
                                  const EdgeInsets.fromLTRB(16, 0, 16, 12),
                              expandedCrossAxisAlignment:
                                  CrossAxisAlignment.start,
                              title: Text(_title(data[i].tag.label),
                                  style:
                                      Niche.ui(16, 22, FontWeight.w700, t.ink)),
                              subtitle: Text(
                                  [
                                    if (data[i].closet.isNotEmpty)
                                      '${data[i].closet.length} in your closet',
                                    '${data[i].products.length} to shop',
                                  ].join(' · '),
                                  style: Niche.ui(
                                      13, 18, FontWeight.w500, t.muted)),
                              children: [
                                if (data[i].closet.isNotEmpty) ...[
                                  label(context, 'You already own'),
                                  row([
                                    for (final c in data[i].closet)
                                      tile(context,
                                          key: ValueKey('similar-own-${c.id}'),
                                          url: widget.api.imageProxyUrl(
                                              ownedClosetPhoto(c)),
                                          title: c.label ?? c.category,
                                          subtitle: c.brand,
                                          onTap: () => Navigator.push<void>(
                                              context,
                                              MaterialPageRoute(
                                                  builder: (_) =>
                                                      ClosetPieceScreen(
                                                          api: widget.api,
                                                          initial: c))))
                                  ]),
                                ],
                                if (data[i].products.isNotEmpty) ...[
                                  label(context, 'Shop similar'),
                                  row([
                                    for (final p in data[i].products)
                                      tile(context,
                                          key: ValueKey(
                                              'similar-shop-${p.product.id}'),
                                          url: widget.api.imageProxyUrl(
                                              p.heroImageUrl ??
                                                  p.product.imageUrl),
                                          title: p.product.name,
                                          subtitle:
                                              '${retailerName(p.product.retailer)} · ${dollars(p.product.effectivePrice)}',
                                          onTap: () => shop([p]))
                                  ]),
                                ],
                                if (data[i].closet.isEmpty &&
                                    data[i].products.isEmpty)
                                  const Padding(
                                      padding: EdgeInsets.all(4),
                                      child: Text('Nothing similar yet.')),
                              ])),
                    if (all.isNotEmpty)
                      Padding(
                          padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                          child: FilledButton(
                              onPressed: () => shop(all),
                              child: const Text('Shop the whole look'))),
                  ]);
            }));
  }
}

class EditTagsDialog extends StatefulWidget {
  const EditTagsDialog({super.key, required this.tags});
  final List<FitTag> tags;
  @override
  State<EditTagsDialog> createState() => _EditTagsDialogState();
}

class _EditTagsDialogState extends State<EditTagsDialog> {
  late final labels = [
    for (final tag in widget.tags) TextEditingController(text: tag.label)
  ];
  @override
  void dispose() {
    for (final c in labels) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
          title: const Text('Edit outfit labels'),
          content: SizedBox(
              width: 400,
              child: SingleChildScrollView(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Text('Correct a label, or clear it to remove that tag.'),
                for (var i = 0; i < labels.length; i++)
                  Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: TextField(
                          controller: labels[i],
                          decoration:
                              InputDecoration(labelText: 'Piece ${i + 1}'))),
              ]))),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () {
                  Navigator.pop(context, [
                    for (var i = 0; i < labels.length; i++)
                      if (labels[i].text.trim().isNotEmpty)
                        FitTag.fromJson({
                          ...widget.tags[i].toJson(),
                          'label': labels[i].text.trim()
                        })
                  ]);
                },
                child: const Text('Save tags'))
          ]);
}

class CatalogTag extends StatefulWidget {
  const CatalogTag(
      {super.key,
      required this.api,
      required this.tag,
      required this.onProduct,
      this.onSearch});
  final Api api;
  final FitTag tag;
  final void Function(Product) onProduct;
  final void Function(String)? onSearch;
  @override
  State<CatalogTag> createState() => _CatalogTagState();
}

class _CatalogTagState extends State<CatalogTag> {
  late final Future<Product?> product = widget.tag.productId == null
      ? Future.value(null)
      : widget.api
          .product(widget.tag.productId!)
          .then<Product?>((p) => p)
          .catchError((_) => null);
  @override
  Widget build(BuildContext context) => FutureBuilder<Product?>(
      future: product,
      builder: (context, snapshot) {
        final p = snapshot.data;
        return NichePress(
            child: NicheGlass(
                radius: 999,
                opacity: .75,
                child: ActionChip(
                    label: Text(p == null
                        ? '${widget.tag.label}${widget.tag.retailer == null ? '' : ' · ${retailerName(widget.tag.retailer!)}'}'
                        : '${p.name} · ${retailerName(p.retailer)} · ${dollars(p.effectivePrice)}'),
                    onPressed: () => p == null
                        ? widget.onSearch?.call(widget.tag.label)
                        : widget.onProduct(p))));
      });
}
