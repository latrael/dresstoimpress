import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollCacheExtent;

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
    this.automaticSizing = false,
    this.hasSizingProfile = false,
    this.onSizingSetup,
    this.sizingRevision = 0,
    this.onTryOn,
    this.onCompleteLook,
  });

  final List<Map<String, dynamic>> products;
  final Set<String> savedIds;
  final Future<void> Function(String id, bool saved) onSave;
  final Future<void> Function(String id, String size) onAddToCart;
  final String Function(String source) imageUrl;

  final bool automaticSizing;
  final bool hasSizingProfile;
  final int sizingRevision;
  final Future<void> Function()? onSizingSetup;
  final Future<String?> Function(String id)? onSizeAdvice;
  final Future<({String url, String label})?> Function(String id)? onTryOn;
  final void Function(String id)? onCompleteLook;

  @override
  State<QuickBrowse> createState() => _QuickBrowseState();
}

class _QuickBrowseState extends State<QuickBrowse> {
  @override
  Widget build(BuildContext context) {
    if (widget.products.isEmpty) {
      return const Center(child: Text('No pieces to browse yet.'));
    }
    return LayoutBuilder(builder: (context, viewport) {
      return ListView.separated(
        key: const ValueKey('product-stream'),
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 112),
        // Build the visible products and roughly one screen ahead/behind.
        scrollCacheExtent: const ScrollCacheExtent.viewport(1),
        itemCount: widget.products.length,
        separatorBuilder: (context, index) => Container(
          key: ValueKey('product-separator-$index'),
          height: 1,
          margin: const EdgeInsets.symmetric(vertical: 24),
          color: const Color(0xFFBDA7AD),
        ),
        itemBuilder: (context, index) => _ProductPage(
          key: ValueKey(widget.products[index]['id']),
          product: widget.products[index],
          saved: widget.savedIds.contains(widget.products[index]['id']),
          onSave: widget.onSave,
          onAddToCart: widget.onAddToCart,
          imageUrl: widget.imageUrl,
          onSizeAdvice: widget.onSizeAdvice,
          automaticSizing: widget.automaticSizing,
          hasSizingProfile: widget.hasSizingProfile,
          onSizingSetup: widget.onSizingSetup,
          sizingRevision: widget.sizingRevision,
          onTryOn: widget.onTryOn,
          onCompleteLook: widget.onCompleteLook,
          imageHeight: (viewport.maxHeight * .46).clamp(180.0, 390.0),
          nextImage: index + 1 < widget.products.length
              ? widget.products[index + 1]['image_url'] as String?
              : null,
        ),
      );
    });
  }
}

class _ProductPage extends StatefulWidget {
  const _ProductPage({
    super.key,
    required this.product,
    required this.saved,
    required this.onSave,
    required this.onAddToCart,
    required this.imageUrl,
    this.nextImage,
    required this.imageHeight,
    this.onSizeAdvice,
    required this.automaticSizing,
    required this.hasSizingProfile,
    required this.onSizingSetup,
    required this.sizingRevision,
    this.onTryOn,
    this.onCompleteLook,
  });
  final Map<String, dynamic> product;
  final bool saved;
  final Future<void> Function(String, bool) onSave;
  final Future<void> Function(String, String) onAddToCart;
  final String Function(String) imageUrl;
  final String? nextImage;
  final double imageHeight;
  final bool automaticSizing;
  final bool hasSizingProfile;
  final int sizingRevision;
  final Future<void> Function()? onSizingSetup;
  final Future<String?> Function(String id)? onSizeAdvice;
  final Future<({String url, String label})?> Function(String id)? onTryOn;
  final void Function(String id)? onCompleteLook;

  @override
  State<_ProductPage> createState() => _ProductPageState();
}

class _ProductPageState extends State<_ProductPage>
    with SingleTickerProviderStateMixin {
  late final heart = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 650));
  bool expandedDescription = false;
  final warmed = <String>{};
  void warm(List<String> gallery) {
    for (final source in [
      if (gallery.isNotEmpty) gallery[photo.clamp(0, gallery.length - 1)],
      if (photo + 1 < gallery.length) gallery[photo + 1],
      if (widget.nextImage != null) widget.nextImage!
    ]) {
      final url = widget.imageUrl(source);
      if (url.isNotEmpty && warmed.add(url)) {
        precacheImage(NetworkImage(url), context, onError: (_, __) {});
      }
    }
  }

  int photo = 0;
  String? size;
  bool saving = false;
  bool adding = false;
  bool advising = false;
  bool generating = false;
  ({String url, String label})? personalPhoto;
  String? error;
  final PageController photos = PageController();
  @override
  void initState() {
    super.initState();
    if (widget.automaticSizing) resolveSize();
  }

  @override
  void didUpdateWidget(covariant _ProductPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.automaticSizing &&
        oldWidget.sizingRevision != widget.sizingRevision) {
      resolveSize();
    }
  }

  int sizeRequest = 0;
  bool alternativeSize = false;
  Future<void> resolveSize() async {
    final request = ++sizeRequest;
    setState(() {
      advising = true;
      alternativeSize = false;
      size = null;
      error = null;
    });
    try {
      if (widget.product['in_your_size'] == false) return;
      final value = widget.product['in_your_size'] == true
          ? widget.product['your_size'] as String?
          : await widget.onSizeAdvice?.call(widget.product['id'] as String);
      if (!mounted || request != sizeRequest) return;
      final sizes = (widget.product['sizes'] as List? ?? []).cast<Map>();
      setState(() {
        size = sizes.any((s) => s['name'] == value && s['in_stock'] == true) &&
                widget.product['in_stock'] != false
            ? value
            : null;
      });
    } catch (_) {
      if (mounted && request == sizeRequest) {
        setState(() =>
            error = 'Could not find your size. Tap Add to Cart to retry.');
      }
    } finally {
      if (mounted && request == sizeRequest) setState(() => advising = false);
    }
  }

  Future<void> automaticAdd() async {
    if (size == null) {
      if ((widget.hasSizingProfile ||
              widget.product['in_your_size'] == false) &&
          error == null) {
        final sizes = (widget.product['sizes'] as List? ?? []).cast<Map>();
        final selected = await showModalBottomSheet<String>(
            context: context,
            useSafeArea: true,
            builder: (context) => Padding(
                padding: const EdgeInsets.all(24),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('Not in your size. Try another fit?'),
                  const SizedBox(height: 16),
                  Wrap(spacing: 8, children: [
                    for (final s in sizes)
                      ChoiceChip(
                          label: Text(s['name'] as String),
                          selected: false,
                          onSelected: s['in_stock'] == true
                              ? (_) =>
                                  Navigator.pop(context, s['name'] as String)
                              : null)
                  ]),
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Keep browsing')),
                ])));
        if (!mounted || selected == null) return;
        setState(() {
          size = selected;
          alternativeSize = true;
        });
      } else {
        if (error == null) await widget.onSizingSetup?.call();
        if (!mounted) return;
        await resolveSize();
      }
    }
    if (mounted && size != null) await add();
  }

  @override
  void dispose() {
    heart.dispose();
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
        if (mounted && photos.hasClients) {
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
    final fullDescription = p['full_description'] as String?;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) warm(gallery);
    });
    final reason = p['reason'] as String?;
    final price = (p['sale_price_usd'] ?? p['price_usd']) as num;
    return Padding(
      key: ValueKey('details-${p['id']}'),
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: widget.imageHeight,
            child: Stack(
              children: [
                Positioned.fill(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: ColoredBox(
                      color: const Color(0xFFEDEAE4),
                      child: GestureDetector(
                        onDoubleTap: () {
                          heart.forward(from: 0);
                          save(value: true);
                        },
                        child: gallery.isEmpty
                            ? const _ImageFailure()
                            : PageView.builder(
                                key: ValueKey('photos-${p['id']}'),
                                controller: photos,
                                itemCount: gallery.length,
                                onPageChanged: (i) => setState(() => photo = i),
                                itemBuilder: (context, i) => Image.network(
                                  widget.imageUrl(gallery[i]),
                                  fit: BoxFit.contain,
                                  webHtmlElementStrategy:
                                      WebHtmlElementStrategy.prefer,
                                  semanticLabel: '${p['name']}, photo ${i + 1}',
                                  errorBuilder: (_, error, stack) =>
                                      const _ImageFailure(),
                                  loadingBuilder: (_, child, progress) =>
                                      progress == null
                                          ? child
                                          : const Center(
                                              child: CircularProgressIndicator(
                                                strokeWidth: 2,
                                              ),
                                            ),
                                ),
                              ),
                      ),
                    ),
                  ),
                ),
                Positioned.fill(
                    child: IgnorePointer(
                        child: AnimatedBuilder(
                  animation: heart,
                  builder: (context, _) => Opacity(
                      opacity: heart.isAnimating
                          ? (heart.value < .55 ? 1 : (1 - heart.value) / .45)
                          : 0,
                      child: Transform.scale(
                          scale: .7 +
                              Curves.easeOutBack.transform(
                                      (heart.value / .4).clamp(0, 1)) *
                                  .3,
                          child: const Icon(Icons.favorite,
                              size: 92,
                              color: Colors.white,
                              shadows: [
                                Shadow(color: Colors.black26, blurRadius: 12)
                              ]))),
                ))),
                Positioned(
                  top: 8,
                  right: 8,
                  child: IconButton.filledTonal(
                    tooltip: widget.saved ? 'Unsave item' : 'Save item',
                    onPressed: saving ? null : save,
                    icon: Icon(
                      widget.saved ? Icons.favorite : Icons.favorite_border,
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
                    style: const TextStyle(fontWeight: FontWeight.w600))),
          const SizedBox(height: 12),
          Text(
            (p['brand'] ?? p['retailer'] ?? '').toString().toUpperCase(),
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
            style: const TextStyle(height: 1.5, color: Color(0xFF57514F)),
          ),
          if (fullDescription != null &&
              fullDescription.trim().isNotEmpty &&
              fullDescription != description) ...[
            if (expandedDescription)
              Text(fullDescription, style: const TextStyle(height: 1.5)),
            TextButton(
                onPressed: () =>
                    setState(() => expandedDescription = !expandedDescription),
                child: Text(expandedDescription ? 'Less' : 'More')),
          ],
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
                child: Text('Color · ${(p['colors'] as List).join(', ')}')),
          const SizedBox(height: 20),
          if (!widget.automaticSizing && widget.onSizeAdvice != null)
            Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                    onPressed: advising ? null : advise,
                    icon: const Icon(Icons.straighten),
                    label: const Text('Find my size'))),
          if (!widget.automaticSizing) ...[
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
                          ? (_) => setState(() => size = s['name'] as String)
                          : null,
                    ),
                  )
                  .toList(),
            ),
          ] else
            Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(advising
                    ? 'Finding your size…'
                    : size != null
                        ? alternativeSize
                            ? 'Size $size · alternative fit'
                            : 'In your size · $size'
                        : (widget.hasSizingProfile ||
                                p['in_your_size'] == false)
                            ? p['your_size'] == null
                                ? 'Not in your size · other fits available'
                                : 'Not in your size · try ${p['your_size']}?'
                            : 'Add your measurements or usual size to find your fit.')),
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
              onPressed: widget.automaticSizing
                  ? (adding || advising || p['in_stock'] == false
                      ? null
                      : automaticAdd)
                  : (size == null || adding ? null : add),
              child: Text(
                adding
                    ? 'Adding…'
                    : widget.automaticSizing
                        ? 'Add to Cart'
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
                        label: Text(
                            generating ? 'Creating try-on…' : 'Try it on')),
                  if (widget.onCompleteLook != null)
                    OutlinedButton.icon(
                        onPressed: () =>
                            widget.onCompleteLook!(p['id'] as String),
                        icon: const Icon(Icons.auto_awesome),
                        label: const Text('Complete the look')),
                ])),
          const SizedBox(height: 14),
        ],
      ),
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
