import 'niche_icons.dart';
import 'dart:typed_data';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/material.dart';

class PickedPhoto {
  const PickedPhoto(this.bytes, this.mimeType);
  final Uint8List bytes;
  final String mimeType;
}

typedef PhotoPicker = Future<PickedPhoto?> Function();
typedef PhotosPicker = Future<List<PickedPhoto>> Function();

Future<PickedPhoto?> pickPhoto() => pickPhotoFrom(ImageSource.gallery);

Future<PickedPhoto?> choosePhoto(BuildContext context) async {
  final source = await showModalBottomSheet<ImageSource>(
      context: context,
      useSafeArea: true,
      builder: (context) => Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(
                leading: const Icon(NicheIcons.cameraAltOutlined),
                title: const Text('Take a photo'),
                onTap: () => Navigator.pop(context, ImageSource.camera)),
            ListTile(
                leading: const Icon(NicheIcons.photoLibraryOutlined),
                title: const Text('Choose from camera roll'),
                onTap: () => Navigator.pop(context, ImageSource.gallery)),
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
          ]));
  return source == null ? null : pickPhotoFrom(source);
}

Future<PickedPhoto?> pickPhotoFrom(ImageSource source) async {
  // Phone photos are 10+ MB; the scan/tagger works from 1600 px, and the server caps at 2048 anyway.
  // Shrinking here turns a 60 s upload through the tunnel into a few seconds.
  final file = await ImagePicker().pickImage(
      source: source, maxWidth: 1600, maxHeight: 1600, imageQuality: 88);
  if (file == null) return null;
  return readPickedPhoto(file);
}

Future<PickedPhoto> readPickedPhoto(XFile file) async {
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

Future<List<PickedPhoto>> choosePhotos(BuildContext context) async {
  final source = await showModalBottomSheet<ImageSource>(
      context: context,
      useSafeArea: true,
      builder: (context) => Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(
                leading: const Icon(NicheIcons.cameraAltOutlined),
                title: const Text('Take a photo'),
                onTap: () => Navigator.pop(context, ImageSource.camera)),
            ListTile(
                leading: const Icon(NicheIcons.photoLibraryOutlined),
                title: const Text('Choose photos from camera roll'),
                onTap: () => Navigator.pop(context, ImageSource.gallery)),
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
          ]));
  if (source == null) return [];
  if (source == ImageSource.camera) {
    final photo = await pickPhotoFrom(source);
    return photo == null ? [] : [photo];
  }
  final files = await ImagePicker()
      .pickMultiImage(maxWidth: 1600, maxHeight: 1600, imageQuality: 88);
  if (files.length > 8) throw Exception('Choose up to eight photos at a time.');
  return Future.wait(files.map(readPickedPhoto));
}
