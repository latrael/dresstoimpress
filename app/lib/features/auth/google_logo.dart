import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Google's four-colour "G", drawn (no asset or SVG package): a ring split red / yellow / green / blue with the
/// opening at the upper right, and the blue bar into the middle. Sized like an icon for "Continue with Google".
class GoogleLogo extends StatelessWidget {
  const GoogleLogo({super.key, this.size = 18});
  final double size;

  @override
  Widget build(BuildContext context) => SizedBox.square(
      dimension: size, child: CustomPaint(painter: _GPainter()));
}

class _GPainter extends CustomPainter {
  static const _blue = Color(0xFF4285F4), _red = Color(0xFFEA4335);
  static const _yellow = Color(0xFFFBBC05), _green = Color(0xFF34A853);

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide, w = s * 0.2;
    final ring =
        Rect.fromCircle(center: Offset(s / 2, s / 2), radius: (s - w) / 2);
    final pen = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = w;
    double rad(double deg) => deg * math.pi / 180;
    // degrees clockwise from 3 o'clock; the gap is 315°-360° (upper right)
    for (final (color, from, to) in [
      (_blue, 0.0, 45.0),
      (_green, 45.0, 135.0),
      (_yellow, 135.0, 210.0),
      (_red, 210.0, 315.0),
    ]) {
      canvas.drawArc(
          ring, rad(from), rad(to - from), false, pen..color = color);
    }
    // the bar: from the centre to the ring's outer edge, level with the centre
    canvas.drawRect(
        Rect.fromLTWH(s / 2, s / 2 - w / 2, s / 2, w), Paint()..color = _blue);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
