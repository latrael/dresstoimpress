import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../store/store_controller.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';
import '../product/complete_look_screen.dart';

class SocialFeed extends StatefulWidget {
  const SocialFeed(
      {super.key,
      required this.store,
      required this.onShop,
      this.picker = pickPhoto});
  final StoreController store;
  final void Function(List<RankedProduct>) onShop;
  final PhotoPicker picker;
  @override
  State<SocialFeed> createState() => _SocialFeedState();
}

class _SocialFeedState extends State<SocialFeed> {
  late Future<List<FitCheckPost>> posts = load();
  Future<List<FitCheckPost>> load() =>
      widget.store.demo ? Future.value([]) : widget.store.api.fitCheckFeed();
  void refresh() => setState(() => posts = load());
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
                            ? 'Connect to see your friends’ fits.'
                            : 'No fits yet. Your next look could be the first.'));
                  }
                  return ListView(padding: const EdgeInsets.all(20), children: [
                    for (final post in snapshot.data!)
                      FitPostCard(
                          key: ValueKey(post.id),
                          post: post,
                          api: widget.store.api,
                          onShop: widget.onShop)
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
            'Share an outfit with your friends. Your photo and caption are uploaded to your connected server; the outfit is tagged automatically.'),
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
            child: Text(busy ? 'Posting and tagging…' : 'Post to Fit Check')),
        if (error != null) Text(error!),
      ]));
}

class FitPostCard extends StatefulWidget {
  const FitPostCard(
      {super.key, required this.post, required this.api, required this.onShop});
  final FitCheckPost post;
  final Api api;
  final void Function(List<RankedProduct>) onShop;
  @override
  State<FitPostCard> createState() => _FitPostCardState();
}

class _FitPostCardState extends State<FitPostCard> {
  late FitCheckPost post = widget.post;
  late bool liked = post.likedByMe ?? false;
  late int count = post.likeCount ?? post.likes.length;
  late List<FitCheckComment> comments = [...post.comments];
  final comment = TextEditingController();
  String? busy;
  String? error;
  FitScore? score;
  @override
  void didUpdateWidget(covariant FitPostCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.post, widget.post)) {
      post = widget.post;
      liked = post.likedByMe ?? false;
      count = post.likeCount ?? post.likes.length;
      comments = [...post.comments];
    }
  }

  @override
  void dispose() {
    comment.dispose();
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

  Future<void> like() => action('update like', () async {
        final result = await widget.api.likeFitCheck(post.id);
        if (mounted) {
          setState(() {
            liked = result.liked;
            count = result.likeCount;
          });
        }
      });
  Future<void> sendComment() => action('send comment', () async {
        final text = comment.text.trim();
        if (text.isEmpty || text.length > 280) return;
        final result = await widget.api.commentFitCheck(post.id, text);
        if (mounted) {
          setState(() {
            comments = [...comments, result];
            comment.clear();
          });
        }
      });
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
      padding: const EdgeInsets.only(bottom: 28),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(post.authorName ?? post.userId)),
        AspectRatio(
            aspectRatio: .85,
            child: ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: PiecePhoto(
                    url: widget.api.imageProxyUrl(post.photoUrl),
                    label: 'Outfit by ${post.authorName ?? post.userId}'))),
        if (post.caption?.isNotEmpty == true)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(post.caption!)),
        if (post.tagged.isNotEmpty)
          Wrap(spacing: 6, children: [
            for (final tag in post.tagged) Chip(label: Text(tag.label))
          ]),
        Wrap(
            spacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              TextButton.icon(
                  onPressed: busy == null ? like : null,
                  icon: Icon(liked ? Icons.favorite : Icons.favorite_border),
                  label: Text('$count')),
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
        if (comments.isNotEmpty) ...[
          const Text('Comments', style: TextStyle(fontWeight: FontWeight.w600)),
          for (final c in comments)
            Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text('${c.userId} · ${c.text}'))
        ],
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
              child: TextField(
                  controller: comment,
                  enabled: busy == null,
                  maxLength: 280,
                  decoration:
                      const InputDecoration(labelText: 'Add a comment'))),
          IconButton(
              tooltip: 'Send comment',
              onPressed: busy == null ? sendComment : null,
              icon: const Icon(Icons.send_outlined))
        ]),
        if (busy != null) const LinearProgressIndicator(),
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
