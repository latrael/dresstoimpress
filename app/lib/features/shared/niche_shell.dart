import 'dart:ui';
import 'package:flutter/material.dart';
import 'niche_theme.dart';
import 'niche_icons.dart';

class NicheHeader extends StatefulWidget {
  const NicheHeader(
      {super.key,
      required this.count,
      required this.initial,
      required this.onLiked,
      required this.onCart,
      required this.onCloset,
      required this.onUser});
  final int count;
  final String initial;
  final VoidCallback onLiked, onCart, onCloset, onUser;
  @override
  State<NicheHeader> createState() => _NicheHeaderState();
}

class _NicheHeaderState extends State<NicheHeader>
    with SingleTickerProviderStateMixin {
  late final bounce = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 300));
  @override
  void didUpdateWidget(covariant NicheHeader oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.count > oldWidget.count && !Niche.reduced(context)) {
      bounce.forward(from: 0);
    }
  }

  @override
  void dispose() {
    bounce.dispose();
    super.dispose();
  }

  Widget action(String label, IconData icon, VoidCallback onTap) => NichePress(
      child: IconButton(
          tooltip: label,
          onPressed: () {
            Niche.select();
            onTap();
          },
          constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
          padding: EdgeInsets.zero,
          icon: Icon(icon, size: 23)));
  @override
  Widget build(BuildContext context) => ClipRect(
      child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: ColoredBox(
              color: Niche.cream.withValues(alpha: .70),
              child: Padding(
                  padding:
                      EdgeInsets.only(top: MediaQuery.paddingOf(context).top),
                  child: SizedBox(
                      height: 56,
                      child: Material(
                          type: MaterialType.transparency,
                          child: Padding(
                              padding:
                                  const EdgeInsets.symmetric(horizontal: 16),
                              child: Row(children: [
                                const Text('niche', style: Niche.wordmark),
                                const Spacer(),
                                action('Liked', NicheIcons.favoriteBorder,
                                    widget.onLiked),
                                AnimatedBuilder(
                                    animation: bounce,
                                    builder: (context, child) =>
                                        Transform.scale(
                                            scale: 1 +
                                                .2 *
                                                    (1 -
                                                        (2 * bounce.value - 1)
                                                            .abs()),
                                            child: child),
                                    child: Badge(
                                        isLabelVisible: widget.count > 0,
                                        backgroundColor: Niche.merlot,
                                        label: AnimatedSwitcher(
                                            duration: const Duration(
                                                milliseconds: 220),
                                            child: Text('${widget.count}',
                                                key: ValueKey(widget.count))),
                                        child: action(
                                            'Your cart',
                                            NicheIcons.shoppingBagOutlined,
                                            widget.onCart))),
                                action('Closet', NicheIcons.checkroomOutlined,
                                    widget.onCloset),
                                const SizedBox(width: 6),
                                NichePress(
                                    child: IconButton(
                                        tooltip: 'User',
                                        onPressed: widget.onUser,
                                        padding: const EdgeInsets.all(6),
                                        constraints: const BoxConstraints(
                                            minWidth: 44, minHeight: 44),
                                        icon: CircleAvatar(
                                            radius: 15,
                                            backgroundColor: Niche.blush,
                                            child: Text(
                                                widget.initial.isEmpty
                                                    ? 'N'
                                                    : widget.initial[0]
                                                        .toUpperCase(),
                                                style: Theme.of(context)
                                                    .textTheme
                                                    .labelMedium!
                                                    .copyWith(
                                                        color: Niche.merlot)))))
                              ]))))))));
}

class NicheNavigation extends StatelessWidget {
  const NicheNavigation(
      {super.key,
      required this.controller,
      required this.index,
      required this.onTap});
  final PageController controller;
  final int index;
  final ValueChanged<int> onTap;
  Widget destination(
      BuildContext context, int value, String label, IconData icon) {
    final selected = index == value;
    final content = Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 22, color: selected ? Niche.cream : Niche.merlot),
      AnimatedSize(
          duration: const Duration(milliseconds: 180),
          child: selected
              ? Padding(
                  padding: const EdgeInsets.only(left: 7),
                  child: Text(label,
                      style: Theme.of(context)
                          .textTheme
                          .labelMedium!
                          .copyWith(color: Niche.cream)))
              : const SizedBox.shrink())
    ]);
    final tap = InkWell(
        key: ValueKey('tab-$value'),
        borderRadius: BorderRadius.circular(999),
        onTap: () {
          Niche.select();
          onTap(value);
        },
        child: SizedBox(
            height: 60,
            child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 7),
                child: Center(
                    child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: ExcludeSemantics(child: content))))));
    return Expanded(
        child: Semantics(
            button: true,
            selected: selected,
            label: label,
            child: NichePress(child: tap)));
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: EdgeInsets.fromLTRB(
          24, 0, 24, NicheInsets.systemBottom(context) + 10),
      child: Center(
          heightFactor: 1,
          child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: DecoratedBox(
                  decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      boxShadow: [
                        BoxShadow(
                            color: Niche.merlot.withValues(alpha: .12),
                            blurRadius: 24,
                            offset: const Offset(0, 8))
                      ]),
                  child: NicheGlass(
                      radius: 999,
                      opacity: .60,
                      blur: 24,
                      child: SizedBox(
                          height: 60,
                          child: AnimatedBuilder(
                              animation: controller,
                              builder: (context, _) {
                                final page = controller.hasClients &&
                                        controller.positions.length == 1
                                    ? controller.page ?? index.toDouble()
                                    : index.toDouble();
                                return LayoutBuilder(
                                    builder: (context, box) => Stack(children: [
                                          Positioned(
                                              left: 8 +
                                                  (box.maxWidth - 16) /
                                                      3 *
                                                      page,
                                              top: 8,
                                              bottom: 8,
                                              width: (box.maxWidth - 16) / 3,
                                              child: DecoratedBox(
                                                  decoration: BoxDecoration(
                                                      color: Niche.merlot,
                                                      borderRadius:
                                                          BorderRadius.circular(
                                                              999)))),
                                          Padding(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                      horizontal: 8),
                                              child: Row(children: [
                                                destination(context, 0, 'Home',
                                                    NicheIcons.homeOutlined),
                                                destination(
                                                    context,
                                                    1,
                                                    'Discover',
                                                    NicheIcons.exploreOutlined),
                                                destination(context, 2, 'Inspo',
                                                    NicheIcons.peopleOutline)
                                              ]))
                                        ]));
                              })))))));
}
