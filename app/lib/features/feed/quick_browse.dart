import 'package:flutter/material.dart';

/// Route adapters belong to the shared shell. Browsing emits no swipe events.
class QuickBrowse extends StatefulWidget {
  const QuickBrowse({
    super.key,
    required this.products,
    required this.savedIds,
    required this.onSave,
    required this.onAddToCart,
    required this.imageUrl,
  });

  final List<Map<String, dynamic>> products;
  final Set<String> savedIds;
  final Future<void> Function(String id, bool saved) onSave;
  final Future<void> Function(String id, String size) onAddToCart;
  final String Function(String source) imageUrl;

  @override
  State<QuickBrowse> createState() => _QuickBrowseState();
}

class _QuickBrowseState extends State<QuickBrowse> {
  final pages = PageController();
  bool paging = false;
  int active = 0;

  @override
  void dispose() {
    pages.dispose();
    super.dispose();
  }

  Future<void> move(int index) async {
    if (paging || index < 0 || index >= widget.products.length) return;
    paging = true;
    await pages.animateToPage(
      index,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOut,
    );
    paging = false;
  }

  @override
  Widget build(BuildContext context) {
    if (widget.products.isEmpty) {
      return const Center(child: Text('No pieces to browse yet.'));
    }
    return PageView.builder(
      controller: pages,
      scrollDirection: Axis.vertical,
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
        onBoundary: (direction) => move(index + direction),
        position: '${index + 1} / ${widget.products.length}',
      ),
    );
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
    required this.position,
    required this.onBoundary,
    required this.active,
  });
  final Map<String, dynamic> product;
  final bool saved;
  final Future<void> Function(String, bool) onSave;
  final Future<void> Function(String, String) onAddToCart;
  final String Function(String) imageUrl;
  final String position;
  final void Function(int direction) onBoundary;
  final bool active;

  @override
  State<_ProductPage> createState() => _ProductPageState();
}

class _ProductPageState extends State<_ProductPage> {
  int photo = 0;
  String? size;
  bool saving = false;
  bool adding = false;
  String? error;
  final PageController photos = PageController();

  @override
  void didUpdateWidget(covariant _ProductPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active && !widget.active) {
      photo = 0;
      size = null;
      error = null;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && photos.hasClients) photos.jumpToPage(0);
      });
    }
  }

  @override
  void dispose() {
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
    final sizes = (p['sizes'] as List? ?? []).cast<Map>();
    final description = p['description'] as String?;
    final reason = p['reason'] as String?;
    final price = (p['sale_price_usd'] ?? p['price_usd']) as num;
    return LayoutBuilder(
      builder: (context, constraints) {
        final imageHeight = (constraints.maxHeight * .46).clamp(180.0, 390.0);
        return NotificationListener<OverscrollNotification>(
          onNotification: (notification) {
            if (notification.depth == 0 &&
                notification.metrics.axis == Axis.vertical &&
                notification.overscroll.abs() > 8) {
              widget.onBoundary(notification.overscroll > 0 ? 1 : -1);
            }
            return false;
          },
          child: SingleChildScrollView(
            physics: const ClampingScrollPhysics(),
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
                                        loadingBuilder: (_, child, progress) =>
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
                const SizedBox(height: 20),
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
                          onSelected:
                              s['in_stock'] == true && p['in_stock'] != false
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
                const SizedBox(height: 14),
                Center(
                  child: Text(
                    'Swipe up for the next piece · ${widget.position}',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF736D69),
                    ),
                  ),
                ),
              ],
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
