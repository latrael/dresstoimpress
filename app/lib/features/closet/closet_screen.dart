import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';

class ClosetScreen extends StatefulWidget {
  const ClosetScreen({super.key, required this.api, this.picker = pickPhoto});
  final Api api;
  final PhotoPicker picker;
  @override
  State<ClosetScreen> createState() => _ClosetScreenState();
}

class _ClosetScreenState extends State<ClosetScreen> {
  late Future<List<ClosetItem>> items = widget.api.closet();
  bool busy = false;
  String? message;
  Future<void> upload() async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      final photo = await widget.picker();
      if (photo == null) return;
      final result = await widget.api
          .uploadClosetItem(photo.bytes, mimeType: photo.mimeType);
      if (mounted) {
        setState(() {
          message = result.duplicateOf == null
              ? 'Added to your closet.'
              : 'Added. This may be the same garment as ${result.duplicateOf}; both are saved.';
          items = widget.api.closet();
        });
      }
    } catch (e) {
      if (mounted) setState(() => message = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  /// Digitize wardrobe: one photo of several pieces (flat lay, rack, mirror selfie) adds each one.
  Future<void> scanSeveral() async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      final photo = await widget.picker();
      if (photo == null) return;
      final added = await widget.api
          .digitizeCloset(photo.bytes, mimeType: photo.mimeType);
      if (mounted) {
        final dupes = added.where((i) => i.duplicateOf != null).length;
        setState(() {
          message = added.isEmpty
              ? 'No clothing found in that photo. Try a clearer shot.'
              : 'Added ${added.length} piece${added.length == 1 ? '' : 's'}: ${added.map((i) => i.label ?? i.category).join(', ')}.'
                  '${dupes > 0 ? ' $dupes may already be in your closet.' : ''}';
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
              ],
            ));
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

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your closet',
      child: Column(children: [
        Padding(
            padding: const EdgeInsets.all(20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text(
                  'Add a photo of one garment, or scan a photo of several (a flat lay, your rack, a mirror selfie) to add each piece. Photos are uploaded to your connected server and tagged for outfit suggestions.'),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                FilledButton.icon(
                    onPressed: busy ? null : upload,
                    icon: const Icon(Icons.add_a_photo_outlined),
                    label: Text(busy ? 'Working…' : 'Add a piece')),
                OutlinedButton.icon(
                    onPressed: busy ? null : scanSeveral,
                    icon: const Icon(Icons.document_scanner_outlined),
                    label: const Text('Scan several pieces')),
              ]),
              if (message != null) Text(message!),
            ])),
        Expanded(
            child: FutureBuilder<List<ClosetItem>>(
                future: items,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return Center(
                        child: TextButton(
                            onPressed: () =>
                                setState(() => items = widget.api.closet()),
                            child: const Text('Could not load closet. Retry')));
                  }
                  if (!snapshot.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.data!.isEmpty) {
                    return const Center(
                        child:
                            Text('Your closet is ready for its first piece.'));
                  }
                  return ListView(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      children: [
                        for (final item in snapshot.data!)
                          Card(
                              child: Padding(
                                  padding: const EdgeInsets.all(12),
                                  child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        SizedBox(
                                            height: 210,
                                            width: double.infinity,
                                            child: PiecePhoto(
                                                url: widget.api.imageProxyUrl(
                                                    item.imageUrl),
                                                label: item.label ??
                                                    item.category)),
                                        ListTile(
                                            contentPadding: EdgeInsets.zero,
                                            title: Text(
                                                item.label ?? item.category),
                                            subtitle: Text(
                                                '${item.color} · ${item.category}'),
                                            trailing: IconButton(
                                                tooltip: 'Remove closet piece',
                                                onPressed: busy
                                                    ? null
                                                    : () => remove(item),
                                                icon: const Icon(
                                                    Icons.delete_outline))),
                                        if (item.duplicateOf != null)
                                          const Text(
                                              'Possible duplicate · saved in your closet'),
                                      ])))
                      ]);
                })),
      ]));
}
