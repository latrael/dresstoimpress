import 'package:flutter/foundation.dart';
import '../../core/api.dart';
import '../../core/models.dart';

/// Keeps paged catalog results separate from the suggested feed. A newer query
/// wins even if an older request finishes later.
class CatalogSearch extends ChangeNotifier {
  CatalogSearch(this.api);
  final Api api;
  List<RankedProduct> cards = [];
  int total = 0;
  int? nextOffset;
  String query = '';
  String? error;
  bool loading = false;
  int _version = 0;
  bool _disposed = false;
  Future<void> search(String text) async {
    query = text;
    cards = [];
    total = 0;
    nextOffset = null;
    await _fetch(0, ++_version);
  }

  Future<void> more() async {
    if (loading || nextOffset == null) return;
    await _fetch(nextOffset!, _version);
  }

  Future<void> _fetch(int offset, int version) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final page = await api.searchProducts(q: query, offset: offset);
      if (_disposed || version != _version) return;
      final ids = cards.map((c) => c.id).toSet();
      cards = [
        ...cards,
        for (final p in page.items)
          if (ids.add(p.id)) RankedProduct(product: p)
      ];
      total = page.total;
      nextOffset = page.nextOffset;
    } catch (_) {
      if (!_disposed && version == _version) {
        error = 'Could not search the catalog. Try again.';
      }
    } finally {
      if (!_disposed && version == _version) {
        loading = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
