import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';

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
      {super.key, required this.api, this.picker, this.photosPicker});
  final Api api;
  final PhotoPicker? picker;
  final PhotosPicker? photosPicker;
  @override
  State<ClosetScreen> createState() => _ClosetScreenState();
}

class _ClosetScreenState extends State<ClosetScreen> {
  late Future<List<ClosetItem>> items = widget.api.closet();
  bool busy = false;
  String view = 'pieces';
  String? message;
  void refresh() => setState(() {
        items = widget.api.closet();
      });
  Future<void> chooseUpload() async {
    final kind = await showModalBottomSheet<String>(
        context: context,
        useSafeArea: true,
        builder: (context) => Column(mainAxisSize: MainAxisSize.min, children: [
              ListTile(
                  leading: const Icon(Icons.checkroom_outlined),
                  title: const Text('A piece'),
                  subtitle: const Text('One garment, one or more photos'),
                  onTap: () => Navigator.pop(context, 'piece')),
              ListTile(
                  leading: const Icon(Icons.style_outlined),
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
              const Text(
                  'Your own clothes and the outfits you wore them in. Choose up to eight photos; we find each garment.'),
              const SizedBox(height: 12),
              FilledButton.icon(
                  onPressed: busy ? null : chooseUpload,
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: Text(busy ? 'Finding your pieces…' : 'Add to closet')),
              const SizedBox(height: 12),
              SegmentedButton<String>(segments: const [
                ButtonSegment(
                    value: 'pieces',
                    label: Text('Pieces'),
                    icon: Icon(Icons.checkroom_outlined)),
                ButtonSegment(
                    value: 'outfits',
                    label: Text('Outfits'),
                    icon: Icon(Icons.style_outlined))
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
                    final photos = <String, List<ClosetItem>>{};
                    for (final item in pieces) {
                      for (final worn in item.wornIn) {
                        if (worn.photoUrl.isNotEmpty &&
                            worn.photoUrl != item.catalogImageUrl) {
                          final group =
                              photos.putIfAbsent(worn.photoUrl, () => []);
                          if (!group.any((p) => p.id == item.id)) {
                            group.add(item);
                          }
                        }
                      }
                    }
                    if (photos.isEmpty) {
                      return const Center(
                          child: Text(
                              'Add an outfit photo to see what you wore together.'));
                    }
                    final entries = photos.entries.toList();
                    return GridView.builder(
                        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: 2,
                                crossAxisSpacing: 12,
                                mainAxisSpacing: 12,
                                childAspectRatio: .68),
                        itemCount: entries.length,
                        itemBuilder: (context, i) => Card(
                            clipBehavior: Clip.antiAlias,
                            child: InkWell(
                                onTap: () => Navigator.push<void>(
                                    context,
                                    MaterialPageRoute(
                                        builder: (_) => _ClosetOutfitScreen(
                                            api: widget.api,
                                            photo: entries[i].key,
                                            pieces: entries[i].value))),
                                child: Column(children: [
                                  Expanded(
                                      child: PiecePhoto(
                                          url: widget.api
                                              .imageProxyUrl(entries[i].key),
                                          label: 'Your outfit')),
                                  Padding(
                                      padding: const EdgeInsets.all(12),
                                      child: Text(
                                          '${entries[i].value.length} pieces'))
                                ]))));
                  }
                  return GridView.builder(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              childAspectRatio: .62),
                      itemCount: pieces.length,
                      itemBuilder: (context, i) {
                        final item = pieces[i];
                        return Card(
                            clipBehavior: Clip.antiAlias,
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                      child: InkWell(
                                          onTap: () => openPiece(item),
                                          child: PiecePhoto(
                                              url: widget.api.imageProxyUrl(
                                                  ownedClosetPhoto(item)),
                                              label: item.label ??
                                                  item.category))),
                                  Padding(
                                      padding: const EdgeInsets.fromLTRB(
                                          10, 8, 8, 0),
                                      child: Text(item.label ?? item.category,
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis)),
                                  if (item.brand?.trim().isNotEmpty == true)
                                    Padding(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 10),
                                        child: Text(item.brand!,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: Theme.of(context)
                                                .textTheme
                                                .labelSmall)),
                                  Align(
                                      alignment: Alignment.centerRight,
                                      child: IconButton(
                                          tooltip: 'Remove closet piece',
                                          onPressed:
                                              busy ? null : () => remove(item),
                                          icon:
                                              const Icon(Icons.delete_outline)))
                                ]));
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

class _ClosetOutfitScreen extends StatelessWidget {
  const _ClosetOutfitScreen(
      {required this.api, required this.photo, required this.pieces});
  final Api api;
  final String photo;
  final List<ClosetItem> pieces;
  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your outfit',
      child: ListView(padding: const EdgeInsets.all(20), children: [
        SizedBox(
            height: 420,
            child: PiecePhoto(
                url: api.imageProxyUrl(photo), label: 'Your outfit')),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final p in pieces)
            ActionChip(
                label: Text(p.label ?? p.category),
                onPressed: () => Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                        builder: (_) =>
                            ClosetPieceScreen(api: api, initial: p))))
        ])
      ]));
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
