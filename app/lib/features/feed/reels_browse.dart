import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../shared/niche_theme.dart';
import '../shared/niche_photo.dart';
import '../shared/niche_icons.dart';

/// UI-only contract. Shared core supplies transport and cache statuses when it lands.
typedef ReelTryOn = ({String status, String? url, String? mode});

class ReelsBrowse extends StatefulWidget {
  const ReelsBrowse(
      {super.key,
      required this.products,
      required this.savedIds,
      required this.onSave,
      required this.onAddToCart,
      required this.imageUrl,
      this.onSizeAdvice,
      this.onCloset,
      this.onBodyPhoto,
      this.prepareTryOns,
      this.loadTryOns,
      this.onRefresh,
      this.seedLabel,
      this.onClearSeed,
      this.active = true});
  final List<Map<String, dynamic>> products;
  final Set<String> savedIds;
  final Future<void> Function(String, bool) onSave;
  final Future<void> Function(String, String) onAddToCart;
  final String Function(String) imageUrl;
  final Future<String?> Function(String)? onSizeAdvice;
  final void Function(String?)? onCloset;
  final VoidCallback? onBodyPhoto, onClearSeed;
  final Future<Map<String, ReelTryOn>> Function(List<String>)? prepareTryOns,
      loadTryOns;
  final Future<void> Function()? onRefresh;
  final String? seedLabel;
  final bool active;
  @override
  State<ReelsBrowse> createState() => _ReelsBrowseState();
}

class _ReelsBrowseState extends State<ReelsBrowse> with WidgetsBindingObserver {
  bool foreground = true;
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      prepare();
    } else {
      poll?.cancel();
    }
  }

  final posts = PageController();
  final tryOns = <String, ReelTryOn>{};
  Timer? poll;
  int visible = 0, revision = 0;
  bool statusLoading = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => prepare());
  }

  @override
  void didUpdateWidget(covariant ReelsBrowse oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.products.map((p) => p['id']).join('|') !=
        widget.products.map((p) => p['id']).join('|')) {
      revision++;
      tryOns.clear();
      visible = 0;
      poll?.cancel();
      if (posts.hasClients) posts.jumpToPage(0);
      WidgetsBinding.instance.addPostFrameCallback((_) => prepare());
    } else if (oldWidget.active != widget.active) {
      if (widget.active) {
        prepare();
      } else {
        poll?.cancel();
      }
    }
  }

  @override
  void dispose() {
    revision++;
    WidgetsBinding.instance.removeObserver(this);
    poll?.cancel();
    posts.dispose();
    super.dispose();
  }

  void warm() {
    for (final p in widget.products.skip(visible + 1).take(2)) {
      final url = widget.imageUrl(heroPhoto(p));
      if (url.isNotEmpty) {
        precacheImage(NetworkImage(url), context, onError: (_, __) {});
      }
    }
  }

  String heroPhoto(Map<String, dynamic> p) {
    if ((p['hero_image_url'] as String? ?? '').isNotEmpty) {
      return p['hero_image_url'] as String;
    }
    for (final image in p['images'] as List? ?? []) {
      if (image is Map &&
          image['kind'] == 'product' &&
          image['url'] is String) {
        return image['url'] as String;
      }
    }
    return p['image_url'] as String? ?? '';
  }

  ReelTryOn status(Map<String, dynamic> p) {
    final cached = tryOns[p['id']];
    if (cached != null) return cached;
    final data = p['tryon'];
    return data is Map
        ? (
            status: data['status'] as String? ?? 'none',
            url: data['image_url'] as String?,
            mode: data['mode'] as String?
          )
        : (status: 'none', url: null, mode: null);
  }

  /// Re-request one post's try-on (after "unavailable"); the server retries since nothing was cached.
  Future<void> retry(String productId) async {
    if (widget.prepareTryOns == null) return;
    setState(() => tryOns[productId] = (status: 'pending', url: null, mode: null));
    try {
      final result = await widget.prepareTryOns!([productId]);
      if (mounted) setState(() => tryOns.addAll(result));
    } catch (_) {/* stays unavailable */}
    schedulePoll();
  }

  Future<void> prepare() async {
    if (!mounted || !widget.active || !foreground || widget.products.isEmpty) {
      return;
    }
    warm();
    final run = revision;
    final ids = widget.products
        .skip(visible == 0 ? 0 : visible + 1)
        .take(3)
        .map((p) => p['id'] as String)
        .toList();
    if (widget.prepareTryOns != null && ids.isNotEmpty) {
      try {
        final result = await widget.prepareTryOns!(ids.take(3).toList());
        if (!mounted || run != revision) return;
        setState(() => tryOns.addAll(result));
      } catch (_) {/* Existing images and state remain usable. */}
    }
    // Landing on an already-prefetched post should show its ready image immediately.
    if (mounted &&
        run == revision &&
        widget.active &&
        foreground &&
        widget.loadTryOns != null &&
        !statusLoading &&
        status(widget.products[visible]).status == 'pending') {
      statusLoading = true;
      try {
        final result = await widget
            .loadTryOns!([widget.products[visible]['id'] as String]);
        if (mounted && run == revision) setState(() => tryOns.addAll(result));
      } catch (_) {/* The three-second read-only poll can recover. */} finally {
        statusLoading = false;
      }
    }
    if (mounted && run == revision) schedulePoll();
  }

  void schedulePoll() {
    poll?.cancel();
    if (!mounted ||
        !widget.active ||
        !foreground ||
        widget.loadTryOns == null ||
        widget.products.isEmpty) {
      return;
    }
    final p = widget.products[visible];
    if (status(p).status != 'pending') return;
    poll = Timer(const Duration(seconds: 3), () async {
      if (!mounted || !widget.active || !foreground || statusLoading) return;
      statusLoading = true;
      final run = revision;
      try {
        final result = await widget.loadTryOns!([p['id'] as String]);
        if (mounted && run == revision) setState(() => tryOns.addAll(result));
      } catch (_) {
        /* Polling is read-only; a later poll may recover. */
      } finally {
        statusLoading = false;
        if (mounted && run == revision) schedulePoll();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.products.isEmpty) {
      return const Center(child: Text('Your next favorite is on its way.'));
    }
    Widget feed = PageView.builder(
        key: const ValueKey('product-stream'),
        controller: posts,
        scrollDirection: Axis.vertical,
        physics:
            const AlwaysScrollableScrollPhysics(parent: PageScrollPhysics()),
        itemCount: widget.products.length,
        onPageChanged: (index) {
          Niche.select();
          setState(() => visible = index);
          prepare();
        },
        itemBuilder: (context, i) {
          final p = widget.products[i];
          return _ReelPost(
              key: ValueKey('reel-${p['id']}'),
              product: p,
              hero: widget.imageUrl(heroPhoto(p)),
              tryOn: status(p),
              saved: widget.savedIds.contains(p['id']),
              imageUrl: widget.imageUrl,
              onSave: widget.onSave,
              onAdd: widget.onAddToCart,
              onSizeAdvice: widget.onSizeAdvice,
              onCloset: widget.onCloset,
              onBodyPhoto: widget.onBodyPhoto,
              onRetryTryOn: widget.prepareTryOns == null ? null : retry,
              seedLabel: i == 0 ? widget.seedLabel : null,
              onClearSeed: widget.onClearSeed);
        });
    if (widget.onRefresh != null) {
      feed = RefreshIndicator(onRefresh: widget.onRefresh!, child: feed);
    }
    return feed;
  }
}

class _ReelPost extends StatefulWidget {
  const _ReelPost(
      {super.key,
      required this.product,
      required this.hero,
      required this.tryOn,
      required this.saved,
      required this.imageUrl,
      required this.onSave,
      required this.onAdd,
      this.onSizeAdvice,
      this.onCloset,
      this.onBodyPhoto,
      this.onRetryTryOn,
      this.seedLabel,
      this.onClearSeed});
  final Map<String, dynamic> product;
  final String hero;
  final ReelTryOn tryOn;
  final bool saved;
  final String Function(String) imageUrl;
  final Future<void> Function(String, bool) onSave;
  final Future<void> Function(String, String) onAdd;
  final Future<String?> Function(String)? onSizeAdvice;
  final void Function(String?)? onCloset;
  final VoidCallback? onBodyPhoto, onClearSeed;
  final void Function(String productId)? onRetryTryOn;
  final String? seedLabel;
  @override
  State<_ReelPost> createState() => _ReelPostState();
}

class _ReelPostState extends State<_ReelPost>
    with SingleTickerProviderStateMixin {
  final photos = PageController();
  int slide = 0;
  bool expanded = false, adding = false, added = false, saving = false;
  String? size, error;
  Timer? reset;
  late final heart = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 650));
  String get id => widget.product['id'] as String;
  List<Map> get sizes => (widget.product['sizes'] as List? ?? [])
      .whereType<Map>()
      .where((s) => s['in_stock'] == true)
      .toList();
  @override
  void initState() {
    super.initState();
    final candidate = widget.product['your_size'] as String?;
    if (sizes.any((s) => s['name'] == candidate)) size = candidate;
  }

  @override
  void dispose() {
    photos.dispose();
    heart.dispose();
    reset?.cancel();
    super.dispose();
  }

  /// Double-tap on the photo: like (never un-likes, like Instagram).
  Future<void> like() => _setLiked(true, burst: true);

  /// The heart button bottom-left of the photo: toggles.
  Future<void> toggleLike() => _setLiked(!widget.saved, burst: !widget.saved);

  Future<void> _setLiked(bool value, {required bool burst}) async {
    HapticFeedback.lightImpact();
    if (burst && !Niche.reduced(context)) heart.forward(from: 0);
    if (saving || widget.saved == value) return;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.onSave(id, value);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not save. Double-tap to retry.');
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Future<String?> chooseSize() => showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Make it your fit',
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                const Text(
                    'Choose an available size. You can edit it in your bag.'),
                const SizedBox(height: 20),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final option in sizes)
                    NicheChip(
                        label: option['name'] as String,
                        selected: size == option['name'],
                        onSelected: (_) =>
                            Navigator.pop(context, option['name'] as String))
                ]),
                const SizedBox(height: 24)
              ])));
  Future<void> add() async {
    if (adding || widget.product['in_stock'] == false) return;
    setState(() {
      adding = true;
      error = null;
    });
    try {
      size ??= await widget.onSizeAdvice?.call(id);
      if (!mounted) return;
      if (!sizes.any((s) => s['name'] == size)) size = null;
      size ??= await chooseSize();
      if (!mounted || size == null) return;
      await widget.onAdd(id, size!);
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      setState(() => added = true);
      reset?.cancel();
      reset = Timer(const Duration(seconds: 2), () {
        if (mounted) setState(() => added = false);
      });
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not add to your bag. Please try again.');
      }
    } finally {
      if (mounted) setState(() => adding = false);
    }
  }

  Widget tag(String text) => NicheGlass(
      radius: 999,
      opacity: .82,
      child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          child: Text(text, style: Theme.of(context).textTheme.labelMedium)));
  Widget onYou() {
    final preview = widget.tryOn;
    // Only a real AI edit of the user's photo is ever shown on this slide; no collage, no outfit board.
    if (preview.url?.isNotEmpty == true && preview.mode == 'ai') {
      return Stack(fit: StackFit.expand, children: [
        NichePhoto(
            key: ValueKey(preview.url), url: widget.imageUrl(preview.url!), label: 'On you'),
        Positioned(left: 16, bottom: 16, child: tag('on you'))
      ]);
    }
    final pending = preview.status == 'pending';
    final unavailable = preview.status == 'unavailable' || preview.status == 'none';
    return Stack(fit: StackFit.expand, children: [
      ColorFiltered(
          colorFilter: ColorFilter.mode(
              Colors.black.withValues(alpha: pending ? .25 : .45), BlendMode.darken),
          child: NichePhoto(key: ValueKey('hero-${widget.hero}'), url: widget.hero, label: 'Product')),
      if (pending) const Positioned.fill(child: NicheShimmer(label: 'Dressing you…')),
      Positioned(
          left: 16,
          right: 16,
          bottom: 16,
          child: Row(children: [
            tag(pending
                ? 'Try-on rendering…'
                : preview.status == 'needs_photo'
                    ? 'Add a photo to see this on you'
                    : 'Try-on unavailable'),
            const Spacer(),
            if (preview.status == 'needs_photo' && widget.onBodyPhoto != null)
              FilledButton.tonal(onPressed: widget.onBodyPhoto, child: const Text('Add photo'))
            else if (unavailable && widget.onRetryTryOn != null)
              FilledButton.tonal(
                  onPressed: () => widget.onRetryTryOn!(widget.product['id'] as String),
                  child: const Text('Retry')),
          ]))
    ]);
  }

  Widget closet() {
    final picks = (widget.product['closet_picks'] as List? ?? [])
        .whereType<Map>()
        .take(4)
        .toList();
    return ColoredBox(
        color: Niche.of(context).paper,
        child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(children: [
              Padding(
                  padding: const EdgeInsets.fromLTRB(4, 20, 4, 12),
                  child: Row(children: [
                    Expanded(
                        child: Text('Already yours.',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.headlineSmall)),
                    const Icon(NicheIcons.checkroomOutlined)
                  ])),
              Expanded(
                  child: LayoutBuilder(
                      builder: (context, box) => Center(
                          child: SizedBox.square(
                              dimension: math.min(box.maxWidth, box.maxHeight),
                              child: GridView.builder(
                                  physics: const NeverScrollableScrollPhysics(),
                                  padding: EdgeInsets.zero,
                                  gridDelegate:
                                      const SliverGridDelegateWithFixedCrossAxisCount(
                                          crossAxisCount: 2,
                                          mainAxisSpacing: 8,
                                          crossAxisSpacing: 8),
                                  itemCount: 4,
                                  itemBuilder: (context, i) {
                                    final pick =
                                        i < picks.length ? picks[i] : null;
                                    final raw =
                                        pick?['image_url'] as String? ?? '';
                                    final own = Uri.tryParse(raw)
                                                ?.path
                                                .startsWith('/static/') ==
                                            true
                                        ? raw
                                        : '';
                                    return NichePress(
                                        child: InkWell(
                                            borderRadius:
                                                BorderRadius.circular(14),
                                            onTap: widget.onCloset == null
                                                ? null
                                                : () {
                                                    Niche.select();
                                                    widget.onCloset!(
                                                        pick?['id'] as String?);
                                                  },
                                            child: ClipRRect(
                                                borderRadius:
                                                    BorderRadius.circular(14),
                                                child: pick == null
                                                    ? DecoratedBox(
                                                        decoration: BoxDecoration(
                                                            color: Niche.of(
                                                                    context)
                                                                .blush,
                                                            borderRadius:
                                                                BorderRadius
                                                                    .circular(
                                                                        14)),
                                                        child: const Center(
                                                            child: Column(
                                                                mainAxisSize:
                                                                    MainAxisSize
                                                                        .min,
                                                                children: [
                                                              Icon(NicheIcons
                                                                  .add),
                                                              SizedBox(
                                                                  height: 8),
                                                              Padding(
                                                                  padding: EdgeInsets
                                                                      .symmetric(
                                                                          horizontal:
                                                                              8),
                                                                  child: Text(
                                                                      'add from your closet',
                                                                      textAlign:
                                                                          TextAlign
                                                                              .center))
                                                            ])))
                                                    : Stack(
                                                        fit: StackFit.expand,
                                                        children: [
                                                            NichePhoto(
                                                                url: widget
                                                                    .imageUrl(
                                                                        own),
                                                                label: pick['label']
                                                                        as String? ??
                                                                    'Your piece'),
                                                            Positioned(
                                                                left: 0,
                                                                right: 0,
                                                                bottom: 0,
                                                                child: NicheGlass(
                                                                    radius: 0,
                                                                    opacity: .8,
                                                                    child: Padding(
                                                                        padding: const EdgeInsets
                                                                            .all(
                                                                            8),
                                                                        child: Text(
                                                                            pick['label'] as String? ??
                                                                                'Your piece',
                                                                            maxLines:
                                                                                1,
                                                                            overflow:
                                                                                TextOverflow.ellipsis,
                                                                            style: Theme.of(context).textTheme.labelSmall))))
                                                          ]))));
                                  })))))
            ])));
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final p = widget.product;
        final bottom = Niche.bottomSpace(context);
        final price = (p['sale_price_usd'] ?? p['price_usd'] ?? 0) as num;
        final photoHeight = math.max(120.0,
            math.min((box.maxWidth - 32) / .8, box.maxHeight - bottom - 174));
        return Padding(
            key: ValueKey('post-$id'),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Stack(children: [
              Positioned(
                  top: 8,
                  left: 0,
                  right: 0,
                  height: photoHeight,
                  child: ClipRRect(
                      borderRadius: BorderRadius.circular(28),
                      child: Stack(fit: StackFit.expand, children: [
                        PageView(
                            controller: photos,
                            key: ValueKey('reel-photos-$id'),
                            physics: const ClampingScrollPhysics(),
                            onPageChanged: (value) {
                              Niche.select();
                              setState(() => slide = value);
                            },
                            children: [
                              GestureDetector(
                                  onDoubleTap: like,
                                  child: NichePhoto(
                                      url: widget.hero,
                                      label: '${p['name']}, the item')),
                              onYou(),
                              closet()
                            ]),
                        Positioned(
                            top: 14,
                            left: 16,
                            right: 16,
                            child: IgnorePointer(
                                child: Row(children: [
                              for (var n = 0; n < 3; n++)
                                Expanded(
                                    child: AnimatedContainer(
                                        duration:
                                            const Duration(milliseconds: 180),
                                        height: 3,
                                        margin: const EdgeInsets.symmetric(
                                            horizontal: 3),
                                        decoration: BoxDecoration(
                                            color: n == slide
                                                ? Colors.white
                                                : Colors.white
                                                    .withValues(alpha: .35),
                                            borderRadius:
                                                BorderRadius.circular(9),
                                            boxShadow: [
                                              BoxShadow(
                                                  color: Niche.ink
                                                      .withValues(alpha: .12),
                                                  blurRadius: 3)
                                            ])))
                            ]))),
                        if (widget.seedLabel != null)
                          Positioned(
                              top: 30,
                              left: 12,
                              right: 12,
                              child: Align(
                                  alignment: Alignment.topLeft,
                                  child: NicheGlass(
                                      radius: 999,
                                      opacity: .85,
                                      child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Flexible(
                                                child: Padding(
                                                    padding:
                                                        const EdgeInsets.only(
                                                            left: 14),
                                                    child: Text(
                                                        'Similar to: ${widget.seedLabel}',
                                                        maxLines: 1,
                                                        overflow: TextOverflow
                                                            .ellipsis))),
                                            IconButton(
                                                tooltip: 'Show all products',
                                                onPressed: widget.onClearSeed,
                                                icon: const Icon(
                                                    NicheIcons.close,
                                                    size: 18))
                                          ])))),
                        IgnorePointer(
                            child: AnimatedBuilder(
                                animation: heart,
                                builder: (context, _) => Opacity(
                                    opacity: heart.isAnimating
                                        ? math.sin(heart.value * math.pi)
                                        : 0,
                                    child: Transform.scale(
                                        scale: .6 + .6 * heart.value,
                                        child: const Center(
                                            child: Icon(NicheIcons.favorite,
                                                size: 88,
                                                color: Niche.paper)))))),
                        Positioned(
                            left: 14,
                            bottom: 14,
                            child: _HeartButton(
                                key: ValueKey('heart-$id'),
                                liked: widget.saved,
                                busy: saving,
                                onTap: toggleLike)),
                      ]))),
              Positioned(
                  left: 0,
                  right: 0,
                  bottom: bottom,
                  child: DecoratedBox(
                      decoration: BoxDecoration(
                          gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                            Niche.of(context).cream.withValues(alpha: 0),
                            Niche.of(context).cream,
                            Niche.of(context).cream
                          ],
                              stops: const [
                            0,
                            .15,
                            1
                          ])),
                      child: Padding(
                          padding: const EdgeInsets.only(top: 16),
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                    (p['brand'] ?? p['retailer'] ?? '')
                                        .toString()
                                        .toUpperCase(),
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelSmall!
                                        .copyWith(color: Niche.wine)),
                                const SizedBox(height: 5),
                                Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Expanded(
                                          child: Text(
                                              p['name'] as String? ?? '',
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: Theme.of(context)
                                                  .textTheme
                                                  .headlineSmall)),
                                      const SizedBox(width: 12),
                                      Padding(
                                          padding:
                                              const EdgeInsets.only(top: 5),
                                          child: Text(
                                              '\$${price.toStringAsFixed(2)}',
                                              style: Niche.price))
                                    ]),
                                NicheReveal(
                                    child: !expanded
                                        ? const SizedBox.shrink()
                                        : ConstrainedBox(
                                            constraints: BoxConstraints(
                                                maxHeight: box.maxHeight * .36),
                                            child: SingleChildScrollView(
                                                child: Padding(
                                                    padding:
                                                        const EdgeInsets.only(
                                                            top: 12),
                                                    child: Column(
                                                        crossAxisAlignment:
                                                            CrossAxisAlignment
                                                                .start,
                                                        children: [
                                                          Text(
                                                              (p['full_description'] ??
                                                                  p[
                                                                      'description'] ??
                                                                  '') as String,
                                                              style: Theme.of(
                                                                      context)
                                                                  .textTheme
                                                                  .bodyLarge),
                                                          if ((p['colors']
                                                                      as List? ??
                                                                  [])
                                                              .isNotEmpty)
                                                            Text(
                                                                'Color · ${(p['colors'] as List).join(', ')}'),
                                                          Row(children: [
                                                            Text(size == null
                                                                ? 'Choose your size'
                                                                : 'Your size: $size'),
                                                            TextButton(
                                                                onPressed:
                                                                    () async {
                                                                  final chosen =
                                                                      await chooseSize();
                                                                  if (mounted &&
                                                                      chosen !=
                                                                          null) {
                                                                    setState(() =>
                                                                        size =
                                                                            chosen);
                                                                  }
                                                                },
                                                                child: const Text(
                                                                    'change'))
                                                          ])
                                                        ]))))),
                                Align(
                                    alignment: Alignment.centerLeft,
                                    child: TextButton(
                                        style: TextButton.styleFrom(
                                            padding: EdgeInsets.zero,
                                            minimumSize: const Size(44, 32)),
                                        onPressed: () {
                                          Niche.select();
                                          setState(() => expanded = !expanded);
                                        },
                                        child: Text(
                                            expanded ? 'less' : 'see more'))),
                                if (error != null)
                                  Padding(
                                      padding: const EdgeInsets.only(bottom: 8),
                                      child: Text(error!,
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall)),
                                SizedBox(
                                    width: double.infinity,
                                    child: NichePress(
                                        child: FilledButton(
                                            onPressed: adding ||
                                                    p['in_stock'] == false ||
                                                    sizes.isEmpty
                                                ? null
                                                : add,
                                            child: AnimatedSwitcher(
                                                duration: const Duration(
                                                    milliseconds: 220),
                                                child: Text(
                                                    adding
                                                        ? 'Adding…'
                                                        : added
                                                            ? 'Added ✓'
                                                            : p['in_stock'] ==
                                                                        false ||
                                                                    sizes
                                                                        .isEmpty
                                                                ? 'Sold out'
                                                                : 'Add to cart',
                                                    key: ValueKey((
                                                      adding,
                                                      added,
                                                      p['in_stock']
                                                    ))))))),
                              ]))))
            ]));
      });
}

/// The physical heart, bottom-left of the photo: a glass circle that fills
/// merlot when liked, with a small bounce on each tap.
class _HeartButton extends StatefulWidget {
  const _HeartButton(
      {super.key,
      required this.liked,
      required this.busy,
      required this.onTap});
  final bool liked, busy;
  final VoidCallback onTap;
  @override
  State<_HeartButton> createState() => _HeartButtonState();
}

class _HeartButtonState extends State<_HeartButton>
    with SingleTickerProviderStateMixin {
  late final bounce = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 260));
  @override
  void dispose() {
    bounce.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
      button: true,
      label: widget.liked ? 'Unlike' : 'Like',
      child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.busy
              ? null
              : () {
                  if (!Niche.reduced(context)) bounce.forward(from: 0);
                  widget.onTap();
                },
          child: AnimatedBuilder(
              animation: bounce,
              builder: (context, child) => Transform.scale(
                  scale: 1 + .22 * math.sin(bounce.value * math.pi),
                  child: child),
              child: NicheGlass(
                  radius: 999,
                  opacity: .82,
                  child: SizedBox(
                      width: 46,
                      height: 46,
                      child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 180),
                          child: Icon(
                              widget.liked
                                  ? NicheIcons.favorite
                                  : NicheIcons.favoriteBorder,
                              key: ValueKey(widget.liked),
                              size: 24,
                              color: widget.liked
                                  ? Niche.wine
                                  : Niche.of(context).ink)))))));
}
