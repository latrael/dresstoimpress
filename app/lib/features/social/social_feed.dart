import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../store/store_controller.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';
import '../product/complete_look_screen.dart';
import '../store/cart_screen.dart';
import '../shared/natural_photo_frame.dart';
import 'comments_sheet.dart';
import 'optimistic_like.dart';
import 'inspo_bindings.dart';

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

class _SocialFeedState extends State<SocialFeed> {
  late Future<List<FitCheckPost>> posts = load();
  Future<List<FitCheckPost>> load() => widget.store.demo
      ? Future.value([])
      : widget.store.api.fitCheckFeed(limit: 100, author: widget.authorId);
  void refresh() => setState(() {
        posts = load();
      });
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
        if (!widget.store.demo)
          Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                IconButton(
                    tooltip: 'Refresh fits',
                    onPressed: refresh,
                    icon: const Icon(Icons.refresh)),
                FilledButton.tonalIcon(
                    onPressed: create,
                    icon: const Icon(Icons.add),
                    label: const Text('Post a fit')),
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
                    return Center(
                        child: Text(widget.store.demo
                            ? 'Connect to explore Inspo.'
                            : 'No fits yet. Your next look could be the first.'));
                  }
                  return ListView(padding: const EdgeInsets.all(20), children: [
                    for (final post in snapshot.data!)
                      FitPostCard(
                          key: ValueKey(post.id),
                          post: post,
                          bindings: widget.bindings,
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
                                          onTagSearch: widget.onTagSearch,
                                          authorId: id,
                                          bindings: widget.bindings)))))
                  ]);
                })),
      ]);
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
          mimeType: photo!.mimeType, caption: caption.text.trim());
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
      title: 'Post a fit',
      child: ListView(padding: const EdgeInsets.all(24), children: [
        const Text(
            'Share an outfit with everyone in Inspo. Your photo and caption are uploaded to your connected server; the outfit is tagged automatically.'),
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

class _FitPostCardState extends State<FitPostCard> {
  late FitCheckPost post = widget.post;
  late bool liked = post.likedByMe ?? false;
  late int count = post.likeCount ?? post.likes.length;
  late List<FitCheckComment> comments = [...post.comments];
  String? busy;
  String? error;
  bool showTags = false;
  bool liking = false;
  OptimisticLike? instantLike;
  late int commentCount = post.commentCount ?? comments.length;
  @override
  void initState() {
    super.initState();
    configureLike();
  }

  void configureLike() {
    if (widget.bindings?.setLike == null) return;
    instantLike = OptimisticLike(
        liked: liked,
        count: count,
        write: (value) => widget.bindings!.setLike!(post.id, value));
    instantLike!.addListener(likeChanged);
  }

  void likeChanged() {
    if (mounted) setState(() {});
  }

  bool get shownLiked => instantLike?.liked ?? liked;
  int get shownCount => instantLike?.count ?? count;

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

  FitScore? score;
  @override
  void didUpdateWidget(covariant FitPostCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.post, widget.post)) {
      post = widget.post;
      liked = post.likedByMe ?? false;
      count = post.likeCount ?? post.likes.length;
      comments = [...post.comments];
      commentCount = post.commentCount ?? comments.length;
      instantLike?.acceptServer(liked, count);
    }
    if (instantLike != null && widget.bindings?.setLike == null) {
      instantLike!.removeListener(likeChanged);
      instantLike!.dispose();
      instantLike = null;
    }
    if (instantLike == null && widget.bindings?.setLike != null) {
      configureLike();
    }
  }

  @override
  void dispose() {
    instantLike?.removeListener(likeChanged);
    instantLike?.dispose();
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

  Future<void> like() async {
    if (instantLike != null) {
      instantLike!.toggle();
      return;
    }
    if (liking) return;
    setState(() {
      liking = true;
      error = null;
    });
    try {
      final result = await widget.api.likeFitCheck(post.id);
      if (mounted) {
        setState(() {
          liked = result.liked;
          count = result.likeCount;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not update like. Please try again.');
      }
    } finally {
      if (mounted) setState(() => liking = false);
    }
  }

  Future<void> openComments() => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => CommentsSheet(
          api: widget.api,
          postId: post.id,
          initial: comments,
          loadPage: widget.bindings?.commentsForPost?.call(post.id),
          authorLabel: widget.bindings?.commentAuthor,
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
  Future<void> editTags() async {
    final result = await showDialog<List<FitTag>>(
        context: context, builder: (_) => EditTagsDialog(tags: post.tagged));
    if (result == null || !mounted) return;
    await action('save tags', () async {
      final updated = await widget.api.updateFitCheckTags(post.id, result);
      if (mounted) {
        setState(() {
          post = updated;
          score = null;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 40),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(post.authorName ?? post.userId),
            onTap: widget.onAuthor == null
                ? null
                : () => widget.onAuthor!(
                    post.userId, post.authorName ?? post.userId),
            trailing: post.userId == widget.api.settings.userId
                ? IconButton(
                    tooltip: 'Delete your post',
                    onPressed: busy == null ? deletePost : null,
                    icon: const Icon(Icons.delete_outline))
                : null),
        NaturalPhotoFrame(
            url: widget.api.imageProxyUrl(post.photoUrl),
            width: widget.bindings?.photoSize?.call(post)?.width,
            height: widget.bindings?.photoSize?.call(post)?.height,
            child: Semantics(
                container: true,
                explicitChildNodes: true,
                button: true,
                label: showTags ? 'Hide outfit tags' : 'Show outfit tags',
                child: GestureDetector(
                    onTap: () => setState(() => showTags = !showTags),
                    child: Stack(fit: StackFit.expand, children: [
                      ClipRRect(
                          borderRadius: BorderRadius.circular(14),
                          child: Image.network(
                              widget.api.imageProxyUrl(post.photoUrl),
                              fit: BoxFit.cover,
                              alignment: Alignment.center,
                              semanticLabel:
                                  'Outfit by ${post.authorName ?? post.userId}',
                              webHtmlElementStrategy:
                                  WebHtmlElementStrategy.prefer,
                              errorBuilder: (_, __, ___) => const Center(
                                  child: Text('Photo unavailable')))),
                      Positioned(
                          left: 12,
                          bottom: 12,
                          right: 12,
                          child: showTags
                              ? Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                      color: const Color(0xEEFFFFF8),
                                      borderRadius: BorderRadius.circular(12)),
                                  constraints:
                                      const BoxConstraints(maxHeight: 180),
                                  child: SingleChildScrollView(
                                      child: Wrap(
                                          spacing: 6,
                                          runSpacing: 6,
                                          children: [
                                        for (final tag in post.tagged)
                                          CatalogTag(
                                              api: widget.api,
                                              tag: tag,
                                              onProduct: (p) => widget.onShop(
                                                  [RankedProduct(product: p)]),
                                              onSearch: widget.onTagSearch)
                                      ])))
                              : const Align(
                                  alignment: Alignment.bottomLeft,
                                  child: Icon(Icons.local_offer_outlined,
                                      color: Colors.white))),
                    ])))),
        if (post.caption?.isNotEmpty == true)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(post.caption!)),
        Wrap(
            spacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              TextButton.icon(
                  key: ValueKey('like-${post.id}'),
                  onPressed: instantLike != null || !liking ? like : null,
                  icon:
                      Icon(shownLiked ? Icons.favorite : Icons.favorite_border),
                  label: Text('$shownCount')),
              FilledButton.tonal(
                  onPressed: busy == null
                      ? () => action('shop this fit', () async {
                            final products =
                                await widget.api.shopFitCheck(post.id);
                            if (mounted) widget.onShop(products);
                          })
                      : null,
                  child: const Text('Shop this fit')),
              TextButton(
                  onPressed: busy == null && post.tagged.isNotEmpty
                      ? () => action('score this fit', () async {
                            final result =
                                await widget.api.fitScore(items: post.tagged);
                            if (mounted) setState(() => score = result);
                          })
                      : null,
                  child: const Text('Fit Score')),
              if (post.userId == widget.api.settings.userId)
                TextButton(
                    onPressed: busy == null ? editTags : null,
                    child: const Text('Edit tags')),
            ]),
        if (score != null) fitScoreCard(score!),
        const SizedBox(height: 12),
        TextButton.icon(
            onPressed: openComments,
            icon: const Icon(Icons.chat_bubble_outline),
            label: Text('Comments ($commentCount)')),
        Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
                onPressed: openComments, child: const Text('Add a comment…'))),
        const SizedBox(height: 16),
        if (busy != null) const LinearProgressIndicator(),
        if (instantLike?.error != null) Text(instantLike!.error!),
        if (error != null) Text(error!),
      ]));
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
        return ActionChip(
            label: Text(p == null
                ? '${widget.tag.label}${widget.tag.retailer == null ? '' : ' · ${retailerName(widget.tag.retailer!)}'}'
                : '${p.name} · ${retailerName(p.retailer)} · ${dollars(p.effectivePrice)}'),
            onPressed: () => p == null
                ? widget.onSearch?.call(widget.tag.label)
                : widget.onProduct(p));
      });
}
