import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Wide images show whole; only portraits taller than 9:16 are center-cropped.
double postPhotoAspect(double width, double height) =>
    width > 0 && height > 0 ? math.max(9 / 16, width / height) : 1;

class NaturalPhotoFrame extends StatefulWidget {
  const NaturalPhotoFrame({super.key, required this.url, required this.child});
  final String url;
  final Widget child;
  @override
  State<NaturalPhotoFrame> createState() => _NaturalPhotoFrameState();
}

class _NaturalPhotoFrameState extends State<NaturalPhotoFrame> {
  double ratio = 1;
  ImageStream? stream;
  ImageStreamListener? listener;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    resolve();
  }

  @override
  void didUpdateWidget(covariant NaturalPhotoFrame oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) {
      ratio = 1;
      resolve();
    }
  }

  void resolve() {
    if (listener != null) stream?.removeListener(listener!);
    if (widget.url.isEmpty) return;
    stream = NetworkImage(widget.url)
        .resolve(createLocalImageConfiguration(context));
    listener = ImageStreamListener((image, synchronous) {
      final next = postPhotoAspect(
          image.image.width.toDouble(), image.image.height.toDouble());
      image.dispose();
      if (!mounted || next == ratio) return;
      if (synchronous) {
        ratio = next;
      } else {
        setState(() => ratio = next);
      }
    }, onError: (_, __) {});
    stream!.addListener(listener!);
  }

  @override
  void dispose() {
    if (listener != null) stream?.removeListener(listener!);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      AspectRatio(aspectRatio: ratio, child: widget.child);
}
