import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../core/api.dart';
import '../../core/models.dart';
import '../profile/shopper_profile.dart';

/// App state and adapters; the shared client remains the only API transport.
class StoreController extends ChangeNotifier {
  StoreController({required this.api, this.demo = true});
  final Api api;
  bool demo;
  bool loading = false;
  String? error;
  String? accountWarning;
  List<RankedProduct> feed = [];
  Set<String> saved = {};
  Cart cart = const Cart(userId: 'u_demo', groups: [], totalUsd: 0, count: 0);
  int _generation = 0;

  int sizingRevision = 0;
  ShopperProfile profile = const ShopperProfile();
  final Map<String, Future<String?>> _sizes = {};
  Future<void> loadProfile() async {
    profile = await ShopperProfile.load(api.settings.userId);
    _sizes.clear();
    sizingRevision++;
    notifyListeners();
  }

  Future<String?> automaticSize(String id) async {
    try {
      return await _cachedSize(id);
    } catch (_) {
      _sizes.remove(id);
      rethrow;
    }
  }

  Future<String?> _cachedSize(String id) => _sizes.putIfAbsent(id, () async {
        final product = feed.where((p) => p.id == id).firstOrNull?.product ??
            (demo ? null : await api.product(id));
        if (product == null || product.inStock == false) return null;
        final available =
            product.sizes.where((s) => s.available).map((s) => s.name).toList();
        if (available.length == 1 &&
            ['ONE SIZE', 'ONESIZE', 'OS']
                .contains(available.single.toUpperCase())) {
          return available.single;
        }
        if (!demo && profile.heightCm != null && profile.weightKg != null) {
          final advice = await api.sizeAdvice(id,
              heightCm: profile.heightCm,
              weightKg: profile.weightKg,
              fit: profile.fit,
              waistIn: profile.waistCm == null ? null : profile.waistCm! / 2.54,
              shoeUs: profile.shoeUs);
          if (advice.size != null && available.contains(advice.size)) {
            return advice.size;
          }
        }
        // An explicit usual size is a fallback, never an invented measurement.
        final match =
            available.where((s) => s.toUpperCase() == profile.usualSize);
        return profile.usualSize.isNotEmpty && match.isNotEmpty
            ? match.first
            : null;
      });

  Future<void> changeSize(CartItem item, String size) async {
    if (size == item.size) return;
    if (demo) {
      final product = item.product!;
      if (!product.sizes.any((s) => s.name == size && s.available)) {
        throw StateError('Size unavailable');
      }
      final items = [
        for (final g in cart.groups)
          for (final i in g.items)
            if (i.productId != item.productId || i.size != item.size) i
      ];
      final index = items
          .indexWhere((i) => i.productId == item.productId && i.size == size);
      final qty = item.qty + (index < 0 ? 0 : items.removeAt(index).qty);
      items.add(CartItem(
          productId: item.productId, size: size, qty: qty, product: product));
      _setDemoCart(items);
      notifyListeners();
      return;
    }
    if (accountWarning != null) throw Exception(accountWarning);
    try {
      // Keep the old line until adding the requested replacement succeeds.
      cart = await api.addToCart(item.productId, size, qty: item.qty);
      cart = await api.removeFromCart(item.productId, size: item.size);
    } catch (_) {
      try {
        cart = await api.cart();
      } catch (_) {
        accountWarning =
            'Cart could not be confirmed. Retry before making changes.';
      }
      throw StateError(
          'Size change could not be confirmed. Review your cart before retrying.');
    } finally {
      notifyListeners();
    }
  }

  Future<void> load() async {
    final generation = ++_generation;
    loading = true;
    error = null;
    accountWarning = null;
    notifyListeners();
    try {
      final cards = demo
          ? (jsonDecode(
                      await rootBundle.loadString('assets/demo-products.json'))
                  as List)
              .map((p) =>
                  RankedProduct.fromJson(Map<String, dynamic>.from(p as Map)))
              .toList()
          : await api.feed();
      if (generation != _generation) return;
      feed = cards;
      if (!demo) {
        try {
          final ids = await api.wishlistIds();
          final latestCart = await api.cart();
          if (generation != _generation) return;
          saved = ids.toSet();
          cart = latestCart;
        } catch (_) {
          if (generation == _generation) {
            accountWarning =
                'Saved items or cart could not be loaded. Retry before making changes.';
          }
        }
      }
    } catch (_) {
      if (generation == _generation) {
        error =
            'Could not load your pieces. Check your connection and try again.';
      }
    } finally {
      if (generation == _generation) {
        loading = false;
        notifyListeners();
      }
    }
  }

  Future<void> useMode(bool isDemo) async {
    demo = isDemo;
    await loadProfile();
    feed = [];
    saved = {};
    cart = Cart(
        userId: api.settings.userId, groups: const [], totalUsd: 0, count: 0);
    await load();
  }

  Future<void> save(String id, bool value) async {
    if (!demo) {
      if (accountWarning != null) throw Exception(accountWarning);
      value ? await api.save(id) : await api.unsave(id);
    }
    saved = {...saved};
    value ? saved.add(id) : saved.remove(id);
    notifyListeners();
  }

  Future<void> add(String id, String size) async {
    if (!demo) {
      if (accountWarning != null) throw Exception(accountWarning);
      cart = await api.addToCart(id, size);
    } else {
      final p = feed.firstWhere((p) => p.id == id).product;
      if (p.inStock == false ||
          !p.sizes.any((s) => s.name == size && s.available)) {
        throw Exception('That size is unavailable. Please choose another.');
      }
      final items = [for (final g in cart.groups) ...g.items];
      final existing =
          items.indexWhere((i) => i.productId == id && i.size == size);
      final qty = existing < 0 ? 1 : items.removeAt(existing).qty + 1;
      items.add(CartItem(productId: id, size: size, qty: qty, product: p));
      _setDemoCart(items);
    }
    notifyListeners();
  }

  Future<void> remove(String id, String size) async {
    if (!demo) {
      cart = await api.removeFromCart(id, size: size);
    } else {
      _setDemoCart([
        for (final g in cart.groups)
          for (final i in g.items)
            if (i.productId != id || i.size != size) i
      ]);
    }
    notifyListeners();
  }

  void _setDemoCart(List<CartItem> items) {
    final retailers = items.map((i) => i.product!.retailer).toSet();
    final groups = [
      for (final retailer in retailers)
        CartGroup(
            retailer: retailer,
            items: items.where((i) => i.product!.retailer == retailer).toList(),
            subtotalUsd: items
                .where((i) => i.product!.retailer == retailer)
                .fold<double>(
                    0, (sum, i) => sum + i.product!.effectivePrice * i.qty))
    ];
    cart = Cart(
        userId: api.settings.userId,
        groups: groups,
        totalUsd: groups.fold(0, (sum, g) => sum + g.subtotalUsd),
        count: items.fold(0, (sum, i) => sum + i.qty));
  }

  Future<CheckoutResult> checkout() async {
    if (demo) {
      final result =
          CheckoutResult(orderId: 'demo', totalUsd: cart.totalUsd, purchases: [
        for (final g in cart.groups)
          Purchase(
              retailer: g.retailer,
              amountUsd: g.subtotalUsd,
              items: const [],
              status: 'demo')
      ]);
      _setDemoCart([]);
      notifyListeners();
      return result;
    }
    final result = await api.checkout();
    // Checkout has completed even if the follow-up cart fetch fails. Never invite
    // a second purchase because a read failed after a successful checkout.
    cart = Cart(
        userId: api.settings.userId, groups: const [], totalUsd: 0, count: 0);
    notifyListeners();
    return result;
  }

  String imageUrl(String source) {
    if (source.isEmpty) return '';
    if (source.startsWith('/')) return api.imageUrl(source);
    if (demo) return source;
    return api.imageProxyUrl(source);
  }
}

Map<String, dynamic> browseMap(RankedProduct card) {
  final p = card.product;
  return {
    'id': p.id,
    'retailer': p.retailer,
    'brand': p.brand ?? p.retailer,
    'name': p.name,
    'price_usd': p.priceUsd,
    'sale_price_usd': p.isOnSale ? p.effectivePrice : null,
    'image_url': p.imageUrl,
    'images': [
      for (final i in p.images) {'url': i.url, 'kind': i.kind}
    ],
    'description': p.description,
    'colors': p.colors,
    'reason': card.reason,
    'in_stock': p.inStock,
    'sizes': [
      for (final s in p.sizes) {'name': s.name, 'in_stock': s.available}
    ],
  };
}
