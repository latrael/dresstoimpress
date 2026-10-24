import 'dart:typed_data';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/material.dart';

class PickedPhoto {
  const PickedPhoto(this.bytes, this.mimeType);
  final Uint8List bytes;
  final String mimeType;
}

typedef PhotoPicker = Future<PickedPhoto?> Function();

Future<PickedPhoto?> pickPhoto() => pickPhotoFrom(ImageSource.gallery);

Future<PickedPhoto?> choosePhoto(BuildContext context) async {
  final source = await showModalBottomSheet<ImageSource>(
      context: context,
      useSafeArea: true,
      builder: (context) => Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(
                leading: const Icon(Icons.camera_alt_outlined),
                title: const Text('Take a photo'),
                onTap: () => Navigator.pop(context, ImageSource.camera)),
            ListTile(
                leading: const Icon(Icons.photo_library_outlined),
                title: const Text('Choose from camera roll'),
                onTap: () => Navigator.pop(context, ImageSource.gallery)),
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
          ]));
  return source == null ? null : pickPhotoFrom(source);
}

Future<PickedPhoto?> pickPhotoFrom(ImageSource source) async {
  final file = await ImagePicker().pickImage(source: source);
  if (file == null) return null;
  if (await file.length() > 10 * 1024 * 1024) {
    throw Exception('Choose a photo smaller than 10 MB.');
  }
  final bytes = await file.readAsBytes();
  String? mime;
  if (bytes.length > 3 &&
      bytes[0] == 0xff &&
      bytes[1] == 0xd8 &&
      bytes[2] == 0xff) {
    mime = 'image/jpeg';
  } else if (bytes.length > 8 &&
      bytes[0] == 137 &&
      bytes[1] == 80 &&
      bytes[2] == 78 &&
      bytes[3] == 71) {
    mime = 'image/png';
  } else if (bytes.length > 12 &&
      String.fromCharCodes(bytes.sublist(0, 4)) == 'RIFF' &&
      String.fromCharCodes(bytes.sublist(8, 12)) == 'WEBP') {
    mime = 'image/webp';
  } else if (bytes.length > 12 &&
      String.fromCharCodes(bytes.sublist(4, 8)) == 'ftyp' &&
      ['heic', 'heix', 'hevc', 'mif1']
          .contains(String.fromCharCodes(bytes.sublist(8, 12)))) {
    mime = 'image/heic';
  }
  if (mime == null) throw Exception('Choose a JPEG, PNG, WebP or HEIC photo.');
  return PickedPhoto(bytes, mime);
}
