import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../fits/fits_screen.dart';
import '../product/complete_look_screen.dart' show fitScoreCard;
import '../shared/feature_ui.dart';
import '../shared/niche_photo.dart';
import '../shared/niche_theme.dart';
import '../shared/pick_photo.dart';
import '../store/store_controller.dart';

/// Catalog images never stand in for something the user owns.
String ownedClosetPhoto(ClosetItem item) {
  for (final url in [item.displayImageUrl, item.cropImageUrl, item.imageUrl]) {
    if (url == null || url.isEmpty || url == item.catalogImageUrl) continue;
    final parsed = Uri.tryParse(url);
    if (parsed != null &&
        !Api.imageProxyHosts.contains(parsed.host) &&
        parsed.path.startsWith('/static/') &&
        parsed.path != '/img') {
      return url;
    }
  }
  return '';
}

class ClosetScreen extends StatefulWidget {
  const ClosetScreen(
      {super.key,
      required this.api,
      this.picker,
      this.photosPicker,
      this.store,
      this.onProduct});
  final Api api;
  final PhotoPicker? picker;
  final PhotosPicker? photosPicker;

  /// With a store, Closet offers "Create 3 fits" (the AI Fit Creator) from your own pieces.
  final StoreController? store;
  final void Function(RankedProduct)? onProduct;
  @override
  State<ClosetScreen> createState() => _ClosetScreenState();
}

class _ClosetScreenState extends State<ClosetScreen> {
  late Future<List<ClosetItem>> items = widget.api.closet();
  Future<List<ClosetOutfit>>? outfits;
  bool busy = false;
  String view = 'pieces';
  String? message;
  void refresh() => setState(() {
        items = widget.api.closet();
        outfits = null;
      });

  void openFits() {
    final store = widget.store;
    if (store == null) return;
    Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => FitsScreen(
                store: store, onProduct: widget.onProduct ?? (_) {})));
  }

  Future<void> chooseUpload() async {
    final kind = await showModalBottomSheet<String>(
        context: context,
        useSafeArea: true,
        builder: (context) => Column(mainAxisSize: MainAxisSize.min, children: [
              ListTile(
                  leading: const Icon(NicheIcons.checkroomOutlined),
                  title: const Text('A piece'),
                  subtitle: const Text('One garment, one or more photos'),
                  onTap: () => Navigator.pop(context, 'piece')),
              ListTile(
                  leading: const Icon(NicheIcons.styleOutlined),
                  title: const Text('An outfit'),
                  subtitle: const Text('Find every garment in your photos'),
                  onTap: () => Navigator.pop(context, 'outfit')),
              TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel')),
            ]));
    if (kind == null || !mounted) return;
    await upload();
  }

  Future<void> upload() async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      List<PickedPhoto> photos;
      if (widget.photosPicker != null) {
        photos = await widget.photosPicker!();
      } else if (widget.picker != null) {
        final photo = await widget.picker!();
        photos = photo == null ? [] : [photo];
      } else {
        photos = await choosePhotos(context);
      }
      if (photos.isEmpty) return;
      // Every upload goes through multi-garment detection, including a single-piece photo.
      final result = await widget.api.uploadClosetPhotos(
          photos.map((p) => p.bytes).toList(),
          kind: 'outfit',
          mimeTypes: photos.map((p) => p.mimeType).toList());
      if (mounted) {
        setState(() {
          outfits = null;
          message =
              '${result.added.length} new piece${result.added.length == 1 ? '' : 's'} added.${result.merged.isEmpty ? '' : ' ${result.merged.length} already in your closet — added these photos to them.'}${result.skipped == 0 ? '' : ' ${result.skipped} photo${result.skipped == 1 ? '' : 's'} could not be tagged.'}';
          items = widget.api.closet();
        });
      }
    } catch (e) {
      if (mounted) setState(() => message = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> remove(ClosetItem item) async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Remove this piece?'),
                content: Text(
                    'Remove ${item.label ?? item.category} from your closet?'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Keep')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Remove'))
                ]));
    if (confirmed != true || !mounted) return;
    setState(() {
      busy = true;
      message = null;
    });
    try {
      await widget.api.deleteClosetItem(item.id);
      if (mounted) {
        setState(() {
          message = 'Removed from your closet.';
          items = widget.api.closet();
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => message = 'Could not remove this piece. Try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openPiece(ClosetItem item) async {
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => ClosetPieceScreen(api: widget.api, initial: item)));
    if (mounted) refresh();
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your closet',
      child: Column(children: [
        Padding(
            padding: const EdgeInsets.all(20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Your clothes and the outfits you wore them in.',
                  style: Niche.ui(
                      14, 20, FontWeight.w500, Niche.of(context).muted)),
              const SizedBox(height: 12),
              Wrap(spacing: 10, runSpacing: 10, children: [
                FilledButton.icon(
                    onPressed: busy ? null : chooseUpload,
                    icon: const Icon(NicheIcons.addAPhotoOutlined),
                    label:
                        Text(busy ? 'Finding your pieces…' : 'Add to closet')),
                if (widget.store != null && !widget.store!.demo)
                  FilledButton.tonalIcon(
                      onPressed: openFits,
                      icon: const Icon(NicheIcons.autoAwesome),
                      label: const Text('Create 3 fits')),
              ]),
              const SizedBox(height: 12),
              SegmentedButton<String>(segments: const [
                ButtonSegment(
                    value: 'pieces',
                    label: Text('Pieces'),
                    icon: Icon(NicheIcons.checkroomOutlined)),
                ButtonSegment(
                    value: 'outfits',
                    label: Text('Outfits'),
                    icon: Icon(NicheIcons.styleOutlined))
              ], selected: {
                view
              }, onSelectionChanged: (v) => setState(() => view = v.single)),
              if (message != null)
                Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(message!)),
            ])),
        Expanded(
            child: FutureBuilder<List<ClosetItem>>(
                future: items,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return Center(
                        child: TextButton(
                            onPressed: refresh,
                            child: const Text('Could not load closet. Retry')));
                  }
                  if (!snapshot.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final pieces = snapshot.data!;
                  if (pieces.isEmpty) {
                    return const Center(
                        child:
                            Text('Your closet is ready for its first piece.'));
                  }
                  if (view == 'outfits') {
                    return _OutfitGrid(
                        api: widget.api,
                        outfits: outfits ??= widget.api.closetOutfits(),
                        onChanged: refresh);
                  }
                  return GridView.builder(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              childAspectRatio: .66),
                      itemCount: pieces.length,
                      itemBuilder: (context, i) {
                        final item = pieces[i];
                        final t = Niche.of(context);
                        return Card(
                            clipBehavior: Clip.antiAlias,
                            child: InkWell(
                                onTap: () => openPiece(item),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Expanded(
                                          child: Stack(
                                              fit: StackFit.expand,
                                              children: [
                                            PiecePhoto(
                                                url: widget.api.imageProxyUrl(
                                                    ownedClosetPhoto(item)),
                                                label: item.label ??
                                                    item.category),
                                            Positioned(
                                                top: 6,
                                                right: 6,
                                                child: NicheGlass(
                                                    radius: 999,
                                                    opacity: .75,
                                                    child: IconButton(
                                                        visualDensity:
                                                            VisualDensity
                                                                .compact,
                                                        iconSize: 18,
                                                        tooltip:
                                                            'Remove closet piece',
                                                        onPressed: busy
                                                            ? null
                                                            : () =>
                                                                remove(item),
                                                        icon: Icon(
                                                            NicheIcons
                                                                .deleteOutline,
                                                            color: t.ink)))),
                                          ])),
                                      Padding(
                                          padding: const EdgeInsets.fromLTRB(
                                              12, 10, 12, 2),
                                          child: Text(
                                              item.label ?? item.category,
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: Niche.ui(13, 18,
                                                  FontWeight.w600, t.ink))),
                                      Padding(
                                          padding: const EdgeInsets.fromLTRB(
                                              12, 0, 12, 12),
                                          child: Text(
                                              item.brand?.trim().isNotEmpty ==
                                                      true
                                                  ? item.brand!
                                                  : item.category,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: Niche.ui(11, 14,
                                                  FontWeight.w600, t.muted))),
                                    ])));
                      });
                })),
      ]));
}

class ClosetPieceScreen extends StatefulWidget {
  const ClosetPieceScreen(
      {super.key, required this.api, required this.initial});
  final Api api;
  final ClosetItem initial;
  @override
  State<ClosetPieceScreen> createState() => _ClosetPieceScreenState();
}

class _ClosetPieceScreenState extends State<ClosetPieceScreen> {
  late ClosetItem item = widget.initial;
  bool busy = false;
  String? error;
  Future<void> update(Future<ClosetItem> Function() task) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final updated = await task();
      if (mounted) setState(() => item = updated);
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> edit() async {
    final edits = await showDialog<Map<String, String>>(
        context: context, builder: (_) => _EditPieceDialog(item: item));
    if (edits == null || !mounted) return;
    await update(() => widget.api.updateClosetItem(item.id,
        label: edits['label'],
        brand: edits['brand'],
        category: edits['category'],
        color: edits['color']));
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: item.label ?? item.category,
      child: ListView(padding: const EdgeInsets.all(20), children: [
        SizedBox(
            height: 360,
            child: PiecePhoto(
                url: widget.api.imageProxyUrl(ownedClosetPhoto(item)),
                label: item.label ?? item.category)),
        if (item.brand?.isNotEmpty == true)
          Text(item.brand!, style: Theme.of(context).textTheme.titleMedium),
        Text('${item.color} · ${item.category}'),
        Wrap(spacing: 8, children: [
          OutlinedButton(
              onPressed: busy ? null : edit, child: const Text('Edit piece')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => update(() => widget.api.reshootClosetItem(item.id)),
              child: const Text('Reshoot piece')),
          if (item.productId != null)
            TextButton(
                onPressed: busy
                    ? null
                    : () => update(() => widget.api
                        .updateClosetItem(item.id, clearProduct: true)),
                child: const Text('Remove catalog match'))
        ]),
        if (busy) const LinearProgressIndicator(),
        if (error != null) Text(error!),
        const SizedBox(height: 24),
        Text('Worn in', style: Theme.of(context).textTheme.titleLarge),
        if (item.wornIn.isEmpty)
          const Text('No outfit photos for this piece yet.'),
        for (final worn in item.wornIn)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: PiecePhoto(
                  url: widget.api.imageProxyUrl(worn.photoUrl),
                  label: 'Your outfit'))
      ]));
}

/// Closet → Outfits: one card per outfit photo (de-duplicated on the server: a photo uploaded to Closet
/// and posted to Inspo is one outfit).
class _OutfitGrid extends StatelessWidget {
  const _OutfitGrid(
      {required this.api, required this.outfits, required this.onChanged});
  final Api api;
  final Future<List<ClosetOutfit>> outfits;
  final VoidCallback onChanged;
  @override
  Widget build(BuildContext context) => FutureBuilder<List<ClosetOutfit>>(
      future: outfits,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
              child: TextButton(
                  onPressed: onChanged,
                  child: const Text('Could not load outfits. Retry')));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final list =
            snapshot.data!.where((o) => o.photoUrl.isNotEmpty).toList();
        if (list.isEmpty) {
          return const Center(
              child:
                  Text('Add an outfit photo to see what you wore together.'));
        }
        final t = Niche.of(context);
        return GridView.builder(
            padding: EdgeInsets.fromLTRB(20, 0, 20, Niche.bottomSpace(context)),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: .66),
            itemCount: list.length,
            itemBuilder: (context, i) {
              final o = list[i];
              final n = o.pieces.length;
              return Card(
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                      onTap: () async {
                        final changed = await Navigator.push<bool>(
                            context,
                            MaterialPageRoute(
                                builder: (_) =>
                                    _ClosetOutfitScreen(api: api, outfit: o)));
                        if (changed == true) onChanged();
                      },
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                                child: Stack(fit: StackFit.expand, children: [
                              NichePhoto(
                                  url: api.imageProxyUrl(o.photoUrl),
                                  label: 'Your outfit'),
                              if (o.posted)
                                Positioned(
                                    top: 8,
                                    left: 8,
                                    child: NicheGlass(
                                        radius: 999,
                                        opacity: .8,
                                        child: Padding(
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 10, vertical: 4),
                                            child: Text('In Inspo',
                                                style: Niche.ui(11, 14,
                                                    FontWeight.w700, t.ink))))),
                            ])),
                            Padding(
                                padding: const EdgeInsets.all(12),
                                child: Text('$n piece${n == 1 ? '' : 's'}',
                                    style: Niche.ui(
                                        13, 18, FontWeight.w600, t.ink)))
                          ])));
            });
      });
}

/// One of your outfits: the photo, its pieces, and its Fit Score (your own outfits only).
class _ClosetOutfitScreen extends StatefulWidget {
  const _ClosetOutfitScreen({required this.api, required this.outfit});
  final Api api;
  final ClosetOutfit outfit;
  @override
  State<_ClosetOutfitScreen> createState() => _ClosetOutfitScreenState();
}

class _ClosetOutfitScreenState extends State<_ClosetOutfitScreen> {
  FitScore? score;
  bool busy = false;
  String? error;
  ClosetOutfit get outfit => widget.outfit;

  Future<void> scoreIt() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.api.fitScore(
          closetItemIds: [for (final p in outfit.pieces) p.id],
          photoUrl: outfit.photoUrl.isEmpty ? null : outfit.photoUrl);
      if (mounted) setState(() => score = result);
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> remove() async {
    final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Remove this outfit?'),
                content: const Text(
                    'The photo leaves your outfits; its pieces stay in your closet.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Keep')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Remove'))
                ]));
    if (yes != true || !mounted) return;
    try {
      await widget.api.deleteClosetOutfit(outfit.id);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    return FeaturePage(
        title: 'Your outfit',
        actions: [
          IconButton(
              tooltip: 'Remove outfit',
              onPressed: remove,
              icon: const Icon(NicheIcons.deleteOutline))
        ],
        child: ListView(
            padding: EdgeInsets.fromLTRB(20, 8, 20, Niche.bottomSpace(context)),
            children: [
              ClipRRect(
                  borderRadius: BorderRadius.circular(Niche.radius),
                  child: AspectRatio(
                      aspectRatio: 3 / 4,
                      child: NichePhoto(
                          url: widget.api.imageProxyUrl(outfit.photoUrl),
                          label: 'Your outfit'))),
              const SizedBox(height: 16),
              if (score != null)
                fitScoreCard(score!)
              else
                FilledButton.tonalIcon(
                    onPressed: busy || outfit.pieces.isEmpty ? null : scoreIt,
                    icon: const Icon(NicheIcons.autoAwesome),
                    label: Text(busy ? 'Scoring…' : 'Fit Score')),
              if (busy) const LinearProgressIndicator(),
              if (error != null) Text(error!),
              const SizedBox(height: 20),
              Text('In this outfit',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              if (outfit.pieces.isEmpty)
                Text('No pieces left from this photo.',
                    style: Niche.ui(14, 20, FontWeight.w500, t.muted)),
              SizedBox(
                  height: 172,
                  child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: outfit.pieces.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 12),
                      itemBuilder: (context, i) {
                        final p = outfit.pieces[i];
                        return SizedBox(
                            width: 104,
                            child: InkWell(
                                borderRadius: BorderRadius.circular(18),
                                onTap: () => Navigator.push<void>(
                                    context,
                                    MaterialPageRoute(
                                        builder: (_) => ClosetPieceScreen(
                                            api: widget.api, initial: p))),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      ClipRRect(
                                          borderRadius:
                                              BorderRadius.circular(18),
                                          child: SizedBox(
                                              height: 128,
                                              width: 104,
                                              child: PiecePhoto(
                                                  url: widget.api.imageProxyUrl(
                                                      ownedClosetPhoto(p)),
                                                  label:
                                                      p.label ?? p.category))),
                                      const SizedBox(height: 6),
                                      Text(p.label ?? p.category,
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                          style: Niche.ui(
                                              12, 16, FontWeight.w600, t.ink)),
                                    ])));
                      })),
            ]));
  }
}

class _EditPieceDialog extends StatefulWidget {
  const _EditPieceDialog({required this.item});
  final ClosetItem item;
  @override
  State<_EditPieceDialog> createState() => _EditPieceDialogState();
}

class _EditPieceDialogState extends State<_EditPieceDialog> {
  late final fields = {
    'label': TextEditingController(text: widget.item.label ?? ''),
    'brand': TextEditingController(text: widget.item.brand ?? ''),
    'category': TextEditingController(text: widget.item.category),
    'color': TextEditingController(text: widget.item.color)
  };
  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
          title: const Text('Edit your piece'),
          content: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
            for (final e in fields.entries)
              Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: TextField(
                      controller: e.value,
                      decoration: InputDecoration(labelText: e.key)))
          ])),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () => Navigator.pop(context, {
                      for (final e in fields.entries) e.key: e.value.text.trim()
                    }),
                child: const Text('Save'))
          ]);
}
