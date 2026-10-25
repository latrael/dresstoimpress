import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';

class BodyPhotoCard extends StatefulWidget {
  const BodyPhotoCard({super.key, required this.api});
  final Api api;
  @override
  State<BodyPhotoCard> createState() => _BodyPhotoCardState();
}

class _BodyPhotoCardState extends State<BodyPhotoCard> {
  late Future<AppUser> user = widget.api.getUser();
  bool busy = false;
  String? error;
  Future<void> remove() async {
    final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Delete your private photo?'),
                content: const Text(
                    'The photo used for try-on and scanning will be deleted. Your confirmed measurements stay.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Keep')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Delete photo'))
                ]));
    if (yes != true || !mounted) return;
    setState(() => busy = true);
    try {
      await widget.api.deleteBodyPhoto();
      if (mounted) setState(() => user = widget.api.getUser());
    } catch (_) {
      if (mounted) setState(() => error = 'Could not delete the photo. Retry.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your private photo',
      child: FutureBuilder<AppUser>(
          future: user,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                  child: TextButton(
                      onPressed: () =>
                          setState(() => user = widget.api.getUser()),
                      child: const Text('Could not load photo. Retry')));
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final url = snapshot.data!.bodyPhotoUrl;
            return ListView(padding: const EdgeInsets.all(24), children: [
              const Text(
                  'Only your account uses this photo for scanning and try-on.'),
              const SizedBox(height: 16),
              if (url == null || url.isEmpty)
                const Text('No private photo saved.')
              else ...[
                SizedBox(
                    height: 400,
                    child: PiecePhoto(
                        url: widget.api.imageProxyUrl(url),
                        label: 'Your private try-on photo')),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                    onPressed: busy ? null : remove,
                    icon: const Icon(NicheIcons.deleteOutline),
                    label: const Text('Delete photo')),
              ],
              if (error != null) Text(error!),
            ]);
          }));
}
