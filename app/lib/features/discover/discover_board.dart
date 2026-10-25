import 'package:flutter/material.dart';

import '../../core/models.dart';
import '../shared/niche_icons.dart';
import '../shared/niche_photo.dart';
import '../shared/niche_theme.dart';
import '../social/social_feed.dart' show FindSimilarSheet;
import '../store/cart_screen.dart' show dollars, retailerName;
import '../store/store_controller.dart';

/// Discover as a Pinterest-style board: style chips on top ("For you" = the user's own styles), then two columns
/// mixing Pinterest outfit pins, things to buy and Inspo outfits (GET /discover/board). Pins and posts have a
/// "Similar" button (the Inspo find-similar sheet: your closet first, then pieces to shop).
class DiscoverBoardView extends StatefulWidget {
  const DiscoverBoardView(
      {super.key,
      required this.store,
      required this.styles,
      required this.onOpen,
      required this.onShop});
  final StoreController store;
  final List<String> styles; // the chips to offer, most common first
  final void Function(RankedProduct) onOpen;
  final void Function(List<RankedProduct>) onShop;
  @override
  State<DiscoverBoardView> createState() => _DiscoverBoardViewState();
}

class _DiscoverBoardViewState extends State<DiscoverBoardView> {
  static const pageSize = 24;
  String? style; // null = For you
  final items = <BoardItem>[];
  int? nextOffset = 0;
  bool loading = false;
  String? error;
  int generation = 0;
  ScrollPosition? scroll;

  @override
  void initState() {
    super.initState();
    load(reset: true);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // the board lives inside Discover's list: load the next page as it nears the end
    scroll?.removeListener(nearEnd);
    scroll = Scrollable.maybeOf(context)?.position?..addListener(nearEnd);
  }

  @override
  void dispose() {
    scroll?.removeListener(nearEnd);
    super.dispose();
  }

  void nearEnd() {
    final p = scroll;
    if (p != null &&
        p.hasContentDimensions &&
        p.pixels > p.maxScrollExtent - 900) {
      load();
    }
  }

  Future<void> load({bool reset = false}) async {
    if (!reset && (loading || nextOffset == null)) return;
    final request = reset ? ++generation : generation;
    setState(() {
      if (reset) {
        items.clear();
        nextOffset = 0;
      }
      loading = true;
      error = null;
    });
    try {
      final page = await widget.store.api.discoverBoard(
          style: style, limit: pageSize, offset: nextOffset ?? 0);
      if (!mounted || request != generation) return;
      setState(() {
        final have = {for (final i in items) i.id};
        items.addAll(page.items.where((i) => have.add(i.id)));
        nextOffset = page.nextOffset;
      });
    } catch (_) {
      if (mounted && request == generation) {
        setState(() => error = 'Could not load the board. Retry');
      }
    } finally {
      if (mounted && request == generation) setState(() => loading = false);
    }
  }

  void pick(String? value) {
    if (value == style) return;
    style = value;
    load(reset: true);
  }

  void similar({Pin? pin, FitCheckPost? post}) => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => FindSimilarSheet(
          api: widget.store.api,
          post: post,
          load: pin == null ? null : () => widget.store.api.pinSimilar(pin.id),
          onShop: widget.onShop));

  /// Each tile goes to the shorter column (by photo aspect), so the two columns stay level like Pinterest.
  (List<BoardItem>, List<BoardItem>) columns() {
    final left = <BoardItem>[], right = <BoardItem>[];
    var lh = 0.0, rh = 0.0;
    for (final item in items) {
      final h = 1 / _aspect(item) + .28; // + the caption under the photo
      if (lh <= rh) {
        left.add(item);
        lh += h;
      } else {
        right.add(item);
        rh += h;
      }
    }
    return (left, right);
  }

  @override
  Widget build(BuildContext context) {
    final (left, right) = columns();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SizedBox(
          height: 44,
          child: ListView(scrollDirection: Axis.horizontal, children: [
            for (final s in <String?>[null, ...widget.styles])
              Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: NicheChip(
                      key: ValueKey('board-style-${s ?? 'for-you'}'),
                      label: s ?? 'For you',
                      selected: style == s,
                      onSelected: (_) => pick(s))),
          ])),
      const SizedBox(height: 16),
      if (items.isEmpty && loading)
        const Padding(
            padding: EdgeInsets.all(32),
            child: Center(child: CircularProgressIndicator()))
      else if (items.isEmpty && error != null)
        TextButton(onPressed: () => load(reset: true), child: Text(error!))
      else if (items.isEmpty)
        const Padding(
            padding: EdgeInsets.all(24),
            child: Text('Nothing here yet. Try another style.'))
      else
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Column(children: [for (final i in left) tile(i)])),
          const SizedBox(width: 10),
          Expanded(child: Column(children: [for (final i in right) tile(i)])),
        ]),
      if (items.isNotEmpty && loading)
        const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator())),
      if (items.isNotEmpty && error != null)
        TextButton(onPressed: load, child: Text(error!)),
    ]);
  }

  static double _aspect(BoardItem i) =>
      (i.pin?.aspect ?? i.post?.photoAspectRatio ?? .75)
          .clamp(9 / 16, 1.2)
          .toDouble();

  Widget tile(BoardItem item) {
    final text = Theme.of(context).textTheme;
    final pin = item.pin, post = item.post, card = item.product;
    final photo = pin?.imageUrl ?? post?.photoUrl ?? card!.product.imageUrl;
    final placeholder = _hex(pin?.dominantColor);
    return Padding(
        key: ValueKey('board-${item.kind}-${item.id}'),
        padding: const EdgeInsets.only(bottom: 14),
        child: NichePress(
            child: InkWell(
                borderRadius: BorderRadius.circular(20),
                onTap: () => card != null
                    ? widget.onOpen(card)
                    : similar(pin: pin, post: post),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ClipRRect(
                          borderRadius: BorderRadius.circular(20),
                          child: AspectRatio(
                              aspectRatio: _aspect(item),
                              child: Stack(fit: StackFit.expand, children: [
                                if (placeholder != null)
                                  ColoredBox(color: placeholder),
                                NichePhoto(
                                    url: widget.store.imageUrl(photo),
                                    label: pin?.title ?? post?.caption ?? ''),
                                if (pin != null || post != null)
                                  Positioned(
                                      right: 8,
                                      bottom: 8,
                                      child: NicheGlass(
                                          radius: 999,
                                          opacity: .85,
                                          child: TextButton.icon(
                                              key: ValueKey(
                                                  'board-similar-${item.id}'),
                                              style: TextButton.styleFrom(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  padding: const EdgeInsets
                                                      .symmetric(
                                                      horizontal: 10)),
                                              onPressed: () =>
                                                  similar(pin: pin, post: post),
                                              icon: const Icon(
                                                  NicheIcons.autoAwesome,
                                                  size: 14),
                                              label: Text('Similar',
                                                  style: text.labelSmall)))),
                              ]))),
                      const SizedBox(height: 6),
                      if (card != null) ...[
                        Text(retailerName(card.product.retailer).toUpperCase(),
                            style:
                                text.labelSmall!.copyWith(color: Niche.wine)),
                        Row(children: [
                          Expanded(
                              child: Text(card.product.name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: text.bodyMedium)),
                          Text(dollars(card.product.effectivePrice),
                              style: Niche.price.copyWith(fontSize: 13)),
                        ]),
                      ] else
                        Text(
                            pin != null
                                ? 'Pinterest · ${pin.style}'
                                : 'Inspo · ${post!.authorName ?? post.userId}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: text.labelSmall),
                    ]))));
  }

  static Color? _hex(String? v) {
    final s = v?.replaceFirst('#', '');
    final n = s == null || s.length != 6 ? null : int.tryParse(s, radix: 16);
    return n == null ? null : Color(0xFF000000 | n);
  }
}
