import 'package:flutter/material.dart';
import 'niche_theme.dart';
import 'niche_icons.dart';

class NichePhoto extends StatelessWidget {
  const NichePhoto(
      {super.key,
      required this.url,
      required this.label,
      this.fit = BoxFit.cover});
  final String url, label;
  final BoxFit fit;
  @override
  Widget build(BuildContext context) => ColoredBox(
      color: Niche.stone,
      child: url.isEmpty
          ? const Center(child: Icon(NicheIcons.imageOutlined))
          : Image.network(url,
              fit: fit,
              width: double.infinity,
              height: double.infinity,
              semanticLabel: label,
              webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
              frameBuilder: (context, child, frame, sync) => AnimatedSwitcher(
                  duration: const Duration(milliseconds: 250),
                  child: frame != null || sync ? child : const NicheShimmer()),
              errorBuilder: (_, __, ___) =>
                  const Center(child: Icon(NicheIcons.imageOutlined))));
}

class NicheShimmer extends StatefulWidget {
  const NicheShimmer({super.key, this.label});
  final String? label;
  @override
  State<NicheShimmer> createState() => _NicheShimmerState();
}

class _NicheShimmerState extends State<NicheShimmer>
    with SingleTickerProviderStateMixin {
  late final motion = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1400));
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (Niche.reduced(context)) {
      motion.stop();
    } else {
      motion.repeat();
    }
  }

  @override
  void dispose() {
    motion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: motion,
      builder: (context, _) => DecoratedBox(
          decoration: BoxDecoration(
              gradient: LinearGradient(
                  begin: Alignment(-2 + motion.value * 4, 0),
                  end: Alignment(motion.value * 4, 0),
                  colors: const [Niche.stone, Niche.paper, Niche.stone])),
          child: Center(
              child: widget.label == null
                  ? null
                  : Text(widget.label!,
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium!
                          .copyWith(color: Niche.muted)))));
}
