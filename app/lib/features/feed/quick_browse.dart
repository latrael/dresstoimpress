import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

typedef _BoundaryCue = ({int direction, double progress, bool touch});

/// Route adapters belong to the shared shell. Browsing emits no swipe events.
class QuickBrowse extends StatefulWidget {
  const QuickBrowse({
    super.key,
    required this.products,
    required this.savedIds,
    required this.onSave,
    required this.onAddToCart,
    required this.imageUrl,
    this.onSizeAdvice,
    this.onTryOn,
    this.onCompleteLook,
  });

  final List<Map<String, dynamic>> products;
  final Set<String> savedIds;
  final Future<void> Function(String id, bool saved) onSave;
  final Future<void> Function(String id, String size) onAddToCart;
  final String Function(String source) imageUrl;

  final Future<String?> Function(String id)? onSizeAdvice;
  final Future<({String url, String label})?> Function(String id)? onTryOn;
  final void Function(String id)? onCompleteLook;

  @override
  State<QuickBrowse> createState() => _QuickBrowseState();
}

class _QuickBrowseState extends State<QuickBrowse> {
  final pages = PageController();
  bool paging = false;
  int active = 0;
  Timer? wheelIdle;
  double wheelDistance = 0;
  bool wheelBurst = false;
  bool wheelEligible = false;
  int? wheelTarget;
  final cue = ValueNotifier<_BoundaryCue?>(null);

  // A wheel/trackpad burst must begin at the details boundary. Momentum from
  // scrolling the description cannot turn into a product change, and a burst
  // can advance only one product even after the next page becomes active.
  void wheel(double delta, bool atBoundary) {
    if (!wheelBurst) {
      wheelBurst = true;
      wheelEligible = atBoundary && !paging;
    }
    if (!atBoundary) {
      wheelEligible = false;
      wheelDistance = 0;
      wheelTarget = null;
      cue.value = null;
    }
    if (paging || !wheelEligible || !atBoundary) return;
    if (wheelDistance.sign != delta.sign) wheelDistance = 0;
    wheelDistance = (wheelDistance + delta).clamp(-160.0, 160.0);
    final target = active + wheelDistance.sign.toInt();
    if (target < 0 || target >= widget.products.length) {
      wheelTarget = null;
      cue.value = null;
      return;
    }
    wheelTarget = wheelDistance.abs() >= 120 ? target : null;
    cue.value = (
      direction: wheelDistance.sign.toInt(),
      progress: (wheelDistance.abs() / 120).clamp(0.0, 1.0),
      touch: false
    );
  }

  void keepWheelAlive(PointerSignalEvent event) {
    if (event is! PointerScrollEvent ||
        event.scrollDelta.dy == 0 ||
        event.scrollDelta.dx.abs() > event.scrollDelta.dy.abs()) {
      return;
    }
    // Wait for the gesture to settle. The arrow stays visible before the page
    // moves, and one continuous trackpad burst can only choose one target.
    wheelIdle?.cancel();
    wheelIdle = Timer(const Duration(milliseconds: 250), () {
      final target = wheelTarget;
      wheelBurst = false;
      wheelDistance = 0;
      wheelTarget = null;
      cue.value = null;
      if (target != null && mounted) move(target);
    });
  }

  void dragCue(double distance) {
    final direction = distance.sign.toInt();
    final target = active + direction;
    if (distance == 0 || target < 0 || target >= widget.products.length) {
      cue.value = null;
    } else {
      cue.value = (
        direction: direction,
        progress: (distance.abs() / 72).clamp(0.0, 1.0),
        touch: true
      );
    }
  }

  @override
  void dispose() {
    wheelIdle?.cancel();
    cue.dispose();
    pages.dispose();
    super.dispose();
  }

  Future<void> move(int index) async {
    if (paging ||
        !pages.hasClients ||
        index < 0 ||
        index >= widget.products.length) {
      return;
    }
    paging = true;
    cue.value = null;
    try {
      await pages.animateToPage(index,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic);
    } finally {
      paging = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.products.isEmpty) {
      return const Center(child: Text('No pieces to browse yet.'));
    }
    return Stack(children: [
      Listener(
        onPointerSignal: keepWheelAlive,
        child: PageView.builder(
          controller: pages,
          scrollDirection: Axis.vertical,
          physics: const NeverScrollableScrollPhysics(),
          onPageChanged: (index) => setState(() => active = index),
          itemCount: widget.products.length,
          itemBuilder: (context, index) => _ProductPage(
            key: ValueKey(widget.products[index]['id']),
            active: index == active,
            product: widget.products[index],
            saved: widget.savedIds.contains(widget.products[index]['id']),
            onSave: widget.onSave,
            onAddToCart: widget.onAddToCart,
            imageUrl: widget.imageUrl,
            onSizeAdvice: widget.onSizeAdvice,
            onTryOn: widget.onTryOn,
            onCompleteLook: widget.onCompleteLook,
            onBoundary: (direction) => move(index + direction),
            onWheel: wheel,
            onDragProgress: dragCue,
            position: '${index + 1} / ${widget.products.length}',
          ),
        ),
      ),
      _BoundaryIndicator(cue: cue),
    ]);
  }
}

class _BoundaryIndicator extends StatelessWidget {
  const _BoundaryIndicator({required this.cue});
  final ValueListenable<_BoundaryCue?> cue;
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<_BoundaryCue?>(
        valueListenable: cue,
        builder: (context, value, _) {
          if (value == null) return const SizedBox.shrink();
          final next = value.direction > 0;
          final item = next ? 'next item' : 'previous item';
          final ready = value.progress >= 1;
          final label = ready
              ? value.touch
                  ? 'Release for $item'
                  : '${next ? 'Next' : 'Previous'} item ready'
              : 'Keep scrolling for $item';
          return Positioned(
            left: 20,
            right: 20,
            bottom: next ? 10 : null,
            top: next ? null : 10,
            child: IgnorePointer(
                child: Center(
                    child: Semantics(
              liveRegion: true,
              child: Material(
                elevation: 4,
                color: Theme.of(context).colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(16),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                  child: SizedBox(
                      width: 260,
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Icon(
                            next
                                ? Icons.keyboard_arrow_up
                                : Icons.keyboard_arrow_down,
                            size: 30),
                        Text(label,
                            textAlign: TextAlign.center,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        LinearProgressIndicator(
                            value: value.progress, minHeight: 3),
                      ])),
                ),
              ),
            ))),
          );
        },
      );
}

class _ProductPage extends StatefulWidget {
  const _ProductPage({
    super.key,
    required this.product,
    required this.saved,
    required this.onSave,
    required this.onAddToCart,
    required this.imageUrl,
    required this.position,
    required this.onBoundary,
    required this.onWheel,
    required this.onDragProgress,
    required this.active,
    this.onSizeAdvice,
    this.onTryOn,
    this.onCompleteLook,
  });
  final Map<String, dynamic> product;
  final bool saved;
  final Future<void> Function(String, bool) onSave;
  final Future<void> Function(String, String) onAddToCart;
  final String Function(String) imageUrl;
  final String position;
  final void Function(int direction) onBoundary;
  final void Function(double delta, bool atBoundary) onWheel;
  final void Function(double distance) onDragProgress;
  final bool active;
  final Future<String?> Function(String id)? onSizeAdvice;
  final Future<({String url, String label})?> Function(String id)? onTryOn;
  final void Function(String id)? onCompleteLook;

  @override
  State<_ProductPage> createState() => _ProductPageState();
}

class _ProductPageState extends State<_ProductPage> {
  int photo = 0;
  String? size;
  bool saving = false;
  bool adding = false;
  bool advising = false;
  bool generating = false;
  ({String url, String label})? personalPhoto;
  String? error;
  final PageController photos = PageController();
  final ScrollController details = ScrollController();
  double dragDistance = 0;
  double dragStart = 0;
  bool dragging = false;

  bool scroll(ScrollNotification notification) {
    // Horizontal photo notifications never participate in product paging.
    if (!widget.active ||
        notification.depth != 0 ||
        notification.metrics.axis != Axis.vertical) {
      return false;
    }
    if (notification is ScrollStartNotification &&
        notification.dragDetails != null) {
      dragging = true;
      dragStart = notification.metrics.pixels;
      dragDistance = 0;
      widget.onDragProgress(0);
    } else if (notification is ScrollUpdateNotification &&
        notification.dragDetails != null) {
      dragDistance = 0;
      widget.onDragProgress(0);
    } else if (notification is OverscrollNotification &&
        notification.dragDetails != null &&
        dragging) {
      final beganAtEdge = notification.overscroll > 0
          ? dragStart >= notification.metrics.maxScrollExtent - 1
          : dragStart <= notification.metrics.minScrollExtent + 1;
      if (beganAtEdge) {
        if (dragDistance.sign != notification.overscroll.sign) dragDistance = 0;
        dragDistance += notification.overscroll;
        widget.onDragProgress(dragDistance);
      }
    } else if (notification is ScrollEndNotification && dragging) {
      dragging = false;
      final direction =
          dragDistance.abs() >= 72 ? dragDistance.sign.toInt() : 0;
      dragDistance = 0;
      if (direction == 0) widget.onDragProgress(0);
      if (direction != 0) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && widget.active) widget.onBoundary(direction);
        });
      }
    }
    return false;
  }

  void pointerSignal(PointerSignalEvent event) {
    if (!widget.active || !details.hasClients || event is! PointerScrollEvent) {
      return;
    }
    final delta = event.scrollDelta;
    if (delta.dy == 0 || delta.dx.abs() > delta.dy.abs()) return;
    final position = details.position;
    final atEdge = delta.dy > 0
        ? position.pixels >= position.maxScrollExtent - 1
        : position.pixels <= position.minScrollExtent + 1;
    widget.onWheel(delta.dy, atEdge);
  }

  @override
  void didUpdateWidget(covariant _ProductPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active && !widget.active) {
      photo = 0;
      size = null;
      error = null;
      dragging = false;
      dragDistance = 0;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          if (photos.hasClients) photos.jumpToPage(0);
          if (details.hasClients) details.jumpTo(0);
        }
      });
    }
  }

  @override
  void dispose() {
    details.dispose();
    photos.dispose();
    super.dispose();
  }

  Future<void> save({bool? value}) async {
    if (saving) return;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.onSave(
        widget.product['id'] as String,
        value ?? !widget.saved,
      );
    } catch (_) {
      if (mounted) setState(() => error = 'Could not save. Please try again.');
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Future<void> add() async {
    if (size == null || adding) return;
    setState(() {
      adding = true;
      error = null;
    });
    try {
      await widget.onAddToCart(widget.product['id'] as String, size!);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Added size $size to cart')));
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => adding = false);
    }
  }

  Future<void> advise() async {
    if (advising) return;
    setState(() => advising = true);
    try {
      final recommended =
          await widget.onSizeAdvice!(widget.product['id'] as String);
      if (!mounted || recommended == null) return;
      final sizes = (widget.product['sizes'] as List? ?? []).cast<Map>();
      if (widget.product['in_stock'] != false &&
          sizes.any((s) => s['name'] == recommended && s['in_stock'] == true)) {
        setState(() => size = recommended);
      } else {
        setState(() => error =
            'That recommendation is no longer available. Choose an in-stock size.');
      }
    } finally {
      if (mounted) setState(() => advising = false);
    }
  }

  Future<void> tryOn() async {
    if (generating) return;
    setState(() {
      generating = true;
      error = null;
    });
    try {
      final result = await widget.onTryOn!(widget.product['id'] as String);
      if (!mounted || result == null) return;
      final retailerPhotos = ((widget.product['images'] as List? ?? [])
              .map((p) => (p as Map)['url'])
              .whereType<String>()
              .where((s) => s.isNotEmpty)
              .toSet())
          .length;
      setState(() => personalPhoto = result);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && widget.active && photos.hasClients) {
          photos.animateToPage(retailerPhotos == 0 ? 1 : retailerPhotos,
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeOut);
        }
      });
    } catch (_) {
      if (mounted) {
        setState(
            () => error = 'Could not create your try-on. Please try again.');
      }
    } finally {
      if (mounted) setState(() => generating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.product;
    final gallery = ((p['images'] as List?) ?? [])
        .map((e) => (e as Map)['url'] as String)
        .where((e) => e.isNotEmpty)
        .toSet()
        .toList();
    if (gallery.isEmpty && (p['image_url'] as String? ?? '').isNotEmpty) {
      gallery.add(p['image_url'] as String);
    }
    if (personalPhoto != null) gallery.add(personalPhoto!.url);
    final sizes = (p['sizes'] as List? ?? []).cast<Map>();
    final description = p['description'] as String?;
    final reason = p['reason'] as String?;
    final price = (p['sale_price_usd'] ?? p['price_usd']) as num;
    return LayoutBuilder(
      builder: (context, constraints) {
        final imageHeight = (constraints.maxHeight * .46).clamp(180.0, 390.0);
        return Listener(
          onPointerSignal: pointerSignal,
          child: NotificationListener<ScrollNotification>(
            onNotification: scroll,
            child: SingleChildScrollView(
              controller: details,
              physics: const AlwaysScrollableScrollPhysics(
                  parent: ClampingScrollPhysics()),
              key: ValueKey('details-${p['id']}'),
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    height: imageHeight,
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(16),
                            child: ColoredBox(
                              color: const Color(0xFFEDEAE4),
                              child: GestureDetector(
                                onDoubleTap: () => save(value: true),
                                child: gallery.isEmpty
                                    ? const _ImageFailure()
                                    : PageView.builder(
                                        key: ValueKey('photos-${p['id']}'),
                                        controller: photos,
                                        itemCount: gallery.length,
                                        onPageChanged: (i) =>
                                            setState(() => photo = i),
                                        itemBuilder: (context, i) =>
                                            Image.network(
                                          widget.imageUrl(gallery[i]),
                                          fit: BoxFit.contain,
                                          webHtmlElementStrategy:
                                              WebHtmlElementStrategy.prefer,
                                          semanticLabel:
                                              '${p['name']}, photo ${i + 1}',
                                          errorBuilder: (_, error, stack) =>
                                              const _ImageFailure(),
                                          loadingBuilder:
                                              (_, child, progress) =>
                                                  progress == null
                                                      ? child
                                                      : const Center(
                                                          child:
                                                              CircularProgressIndicator(
                                                            strokeWidth: 2,
                                                          ),
                                                        ),
                                        ),
                                      ),
                              ),
                            ),
                          ),
                        ),
                        Positioned(
                          top: 8,
                          right: 8,
                          child: IconButton.filledTonal(
                            tooltip: widget.saved ? 'Unsave item' : 'Save item',
                            onPressed: saving ? null : save,
                            icon: Icon(
                              widget.saved
                                  ? Icons.favorite
                                  : Icons.favorite_border,
                            ),
                          ),
                        ),
                        Positioned(
                          bottom: 12,
                          right: 12,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: const Color(0xFF722F42),
                              borderRadius: BorderRadius.circular(9),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (p['sale_price_usd'] != null)
                                  Padding(
                                    padding: const EdgeInsets.only(right: 8),
                                    child: Text(
                                      '\$${(p['price_usd'] as num).toStringAsFixed(2)}',
                                      style: const TextStyle(
                                        color: Colors.white70,
                                        decoration: TextDecoration.lineThrough,
                                      ),
                                    ),
                                  ),
                                Text(
                                  '\$${price.toStringAsFixed(2)}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (gallery.length > 1)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(
                          gallery.length,
                          (i) => Semantics(
                            label: 'Photo ${i + 1} of ${gallery.length}',
                            selected: photo == i,
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              margin: const EdgeInsets.symmetric(horizontal: 3),
                              width: 7,
                              height: 7,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: photo == i
                                    ? const Color(0xFF722F42)
                                    : const Color(0xFFD5C9CB),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (personalPhoto != null && photo == gallery.length - 1)
                    Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(personalPhoto!.label,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600))),
                  const SizedBox(height: 12),
                  Text(
                    (p['brand'] ?? p['retailer'] ?? '')
                        .toString()
                        .toUpperCase(),
                    style: const TextStyle(
                      color: Color(0xFF722F42),
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    p['name'] as String,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    description?.trim().isNotEmpty == true
                        ? description!
                        : 'Description not provided by retailer.',
                    style:
                        const TextStyle(height: 1.5, color: Color(0xFF57514F)),
                  ),
                  if (reason?.trim().isNotEmpty == true)
                    Container(
                      margin: const EdgeInsets.only(top: 14),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF0E5E5),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.auto_awesome,
                            size: 18,
                            color: Color(0xFF722F42),
                          ),
                          const SizedBox(width: 10),
                          Expanded(child: Text(reason!)),
                        ],
                      ),
                    ),
                  if ((p['colors'] as List? ?? []).isNotEmpty)
                    Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text(
                            'Color · ${(p['colors'] as List).join(', ')}')),
                  const SizedBox(height: 20),
                  if (widget.onSizeAdvice != null)
                    Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                            onPressed: advising ? null : advise,
                            icon: const Icon(Icons.straighten),
                            label: const Text('Find my size'))),
                  const Text(
                    'Select size',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: sizes
                        .map(
                          (s) => ChoiceChip(
                            label: Text(s['name'] as String),
                            selected: size == s['name'],
                            onSelected: s['in_stock'] == true &&
                                    p['in_stock'] != false
                                ? (_) =>
                                    setState(() => size = s['name'] as String)
                                : null,
                          ),
                        )
                        .toList(),
                  ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(
                        error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: FilledButton(
                      onPressed: size == null || adding ? null : add,
                      child: Text(
                        adding
                            ? 'Adding…'
                            : size == null
                                ? 'Choose a size'
                                : 'Add to Cart',
                      ),
                    ),
                  ),
                  if (widget.onTryOn != null || widget.onCompleteLook != null)
                    Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Wrap(spacing: 8, children: [
                          if (widget.onTryOn != null)
                            OutlinedButton.icon(
                                onPressed: generating ? null : tryOn,
                                icon: const Icon(Icons.person_outline),
                                label: Text(generating
                                    ? 'Creating try-on…'
                                    : 'Try it on')),
                          if (widget.onCompleteLook != null)
                            OutlinedButton.icon(
                                onPressed: () =>
                                    widget.onCompleteLook!(p['id'] as String),
                                icon: const Icon(Icons.auto_awesome),
                                label: const Text('Complete the look')),
                        ])),
                  const SizedBox(height: 14),
                  Center(
                    child: Text(
                      'Scroll to the bottom, then swipe up · ${widget.position}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF736D69),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _ImageFailure extends StatelessWidget {
  const _ImageFailure();
  @override
  Widget build(BuildContext context) => const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.image_outlined, size: 36),
            SizedBox(height: 8),
            Text('Photo unavailable'),
          ],
        ),
      );
}
