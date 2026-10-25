import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../shared/pick_photo.dart';
import '../shared/feature_ui.dart';

/// Results stay in the current product's gallery, never the shared catalog.
Future<({String url, String label, String? sourcePhotoUrl})?> requestTryOn(
    BuildContext context, Api api, String productId,
    {PhotoPicker picker = pickPhoto}) async {
  final user = await api.getUser();
  if (user.bodyPhotoUrl == null || user.bodyPhotoUrl!.isEmpty) {
    if (!context.mounted) return null;
    final upload = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Add your photo'),
              content: const Text(
                  'Choose a full-body photo for your personal try-on. It will be uploaded to your connected Niche server for this account.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Later')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Choose photo'))
              ],
            ));
    if (upload != true) return null;
    final photo = await picker();
    if (photo == null) return null;
    await api.uploadBodyPhoto(photo.bytes, mimeType: photo.mimeType);
  }
  final result = await api.tryOn([productId]);
  if (result.imageUrl.isEmpty) throw Exception('No preview was returned.');
  return (
    url: result.imageUrl,
    sourcePhotoUrl: result.mode == 'ai' ? result.sourcePhotoUrl : null,
    label: 'Your AI try-on'
  );
}

class BodyPhotoButton extends StatefulWidget {
  const BodyPhotoButton(
      {super.key, required this.api, this.picker = pickPhoto});
  final Api api;
  final PhotoPicker picker;
  @override
  State<BodyPhotoButton> createState() => _BodyPhotoButtonState();
}

class _BodyPhotoButtonState extends State<BodyPhotoButton> {
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
      await widget.api.uploadBodyPhoto(photo.bytes, mimeType: photo.mimeType);
      if (mounted) setState(() => message = 'Your try-on photo is ready.');
    } catch (e) {
      if (mounted) setState(() => message = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text(
            'Your selected photo is uploaded to the connected server for personal try-on.'),
        OutlinedButton.icon(
            onPressed: busy ? null : upload,
            icon: const Icon(NicheIcons.addAPhotoOutlined),
            label: Text(busy ? 'Uploading…' : 'Update try-on photo')),
        if (message != null) Text(message!),
      ]);
}
