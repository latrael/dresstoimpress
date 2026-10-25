import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../shared/niche_theme.dart';
import '../shared/niche_photo.dart';

/// The icon's exact 96-unit geometry, drawn rather than raster-scaled.
class NicheArch extends StatefulWidget {
  const NicheArch({super.key, this.size = 96, this.celebrate = false});
  final double size;
  final bool celebrate;
  @override
  State<NicheArch> createState() => _NicheArchState();
}

class _NicheArchState extends State<NicheArch>
    with SingleTickerProviderStateMixin {
  late final draw = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1100));
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (Niche.reduced(context)) {
      draw.value = 1;
    } else {
      draw.forward();
    }
  }

  @override
  void dispose() {
    draw.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: draw,
      builder: (context, _) => CustomPaint(
          size: Size.square(widget.size), painter: _ArchPainter(draw.value, Niche.of(context).brand)));
}

class _ArchPainter extends CustomPainter {
  const _ArchPainter(this.progress, [this.color = Niche.merlot]);
  final double progress;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 96);
    final path = Path()
      ..moveTo(30, 70)
      ..lineTo(30, 44)
      ..arcTo(const Rect.fromLTWH(30, 26, 36, 36), math.pi, math.pi, false)
      ..lineTo(66, 70);
    final metric = path.computeMetrics().first;
    canvas.drawPath(
        metric.extractPath(0, metric.length * (progress / .7).clamp(0, 1)),
        Paint()
          ..color = color
          ..strokeWidth = 9
          ..strokeCap = StrokeCap.round
          ..style = PaintingStyle.stroke);
    if (progress > .7) {
      final t =
          Curves.easeOutBack.transform(((progress - .7) / .3).clamp(0, 1));
      canvas.drawCircle(Offset(66, 26 - (1 - t) * 18), 5 * t.clamp(0, 1.1),
          Paint()..color = Niche.hook);
    }
  }

  @override
  bool shouldRepaint(covariant _ArchPainter old) => old.progress != progress;
}

class NicheWelcome extends StatefulWidget {
  const NicheWelcome({super.key, required this.photos, required this.onStart});
  final Future<List<String>> photos;
  final VoidCallback onStart;
  @override
  State<NicheWelcome> createState() => _NicheWelcomeState();
}

class _NicheWelcomeState extends State<NicheWelcome>
    with SingleTickerProviderStateMixin {
  late final drift =
      AnimationController(vsync: this, duration: const Duration(seconds: 18));
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (Niche.reduced(context)) {
      drift.stop();
    } else {
      drift.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    drift.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SafeArea(
      top: false,
      child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 20),
          child: Column(children: [
            const _WelcomeDots(),
            const SizedBox(height: 12),
            const NicheArch(size: 94),
            Text('niche',
                style: Niche.wordmark.copyWith(color: Niche.of(context).brand)),
            const SizedBox(height: 22),
            Text("Let's make\nniche yours.",
                style: Theme.of(context).textTheme.displaySmall,
                textAlign: TextAlign.center),
            const SizedBox(height: 12),
            Text('Your style, your size, the clothes you already own.',
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium!
                    .copyWith(color: Niche.of(context).muted)),
            const SizedBox(height: 12),
            Expanded(
                child: FutureBuilder<List<String>>(
                    future: widget.photos,
                    builder: (context, snapshot) {
                      final photos = snapshot.data ?? const <String>[];
                      if (photos.isEmpty) {
                        return const Center(child: NicheArch(size: 140));
                      }
                      return ClipRect(
                          child: ShaderMask(
                              blendMode: BlendMode.dstIn,
                              shaderCallback: (rect) => const LinearGradient(
                                      begin: Alignment.topCenter,
                                      end: Alignment.bottomCenter,
                                      colors: [
                                        Colors.transparent,
                                        Colors.white,
                                        Colors.white,
                                        Colors.transparent
                                      ],
                                      stops: [
                                        0,
                                        .12,
                                        .86,
                                        1
                                      ]).createShader(rect),
                              child: AnimatedBuilder(
                                  animation: drift,
                                  builder:
                                      (context, _) => Row(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              children: [
                                                for (var col = 0;
                                                    col < 3;
                                                    col++)
                                                  Expanded(
                                                      child: Padding(
                                                          padding:
                                                              const EdgeInsets
                                                                  .symmetric(
                                                                  horizontal:
                                                                      4),
                                                          child: Transform
                                                              .translate(
                                                                  offset: Offset(
                                                                      0,
                                                                      -12 -
                                                                          (col + 1) *
                                                                              10 *
                                                                              drift.value),
                                                                  child: OverflowBox(
                                                                      alignment: Alignment.topCenter,
                                                                      maxHeight: 900,
                                                                      child: Column(children: [
                                                                        for (var row =
                                                                                0;
                                                                            row <
                                                                                4;
                                                                            row++)
                                                                          Padding(
                                                                              padding: const EdgeInsets.only(bottom: 8),
                                                                              child: Transform.rotate(angle: (col - 1) * .035, child: SizedBox(height: 148 + (col % 2) * 22.0, child: ClipRRect(borderRadius: BorderRadius.circular(20), child: NichePhoto(url: photos[(row * 3 + col) % photos.length], label: 'A look to make your own')))))
                                                                      ])))))
                                              ]))));
                    })),
            const SizedBox(height: 12),
            SizedBox(
                width: double.infinity,
                child: NichePress(
                    child: FilledButton(
                        onPressed: widget.onStart,
                        child: const Text("Let's go"))))
          ])));
}

class _WelcomeDots extends StatelessWidget {
  const _WelcomeDots();
  @override
  Widget build(BuildContext context) => Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(
          8,
          (i) => Container(
              margin: const EdgeInsets.symmetric(horizontal: 3),
              width: i == 0 ? 22 : 5,
              height: 5,
              decoration: BoxDecoration(
                  color: i == 0 ? Niche.merlot : Niche.of(context).blush,
                  borderRadius: BorderRadius.circular(8)))));
}
