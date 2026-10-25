// Dart mirrors of the backend JSON (backend/app/models.py, NABIL_TO_RYAN.md, ADAM_TO_RYAN.md).
// `fromJson` reads the server's snake_case keys. Anything not always sent is nullable or defaults to
// empty, so a new or missing field never breaks parsing. Pure Dart: no Flutter imports.

typedef Json = Map<String, dynamic>;

String _str(dynamic v, [String fallback = '']) => v == null ? fallback : v.toString();
String? _strN(dynamic v) => v?.toString();
double _dbl(dynamic v, [double fallback = 0]) => v is num ? v.toDouble() : (double.tryParse('$v') ?? fallback);
double? _dblN(dynamic v) => v is num ? v.toDouble() : (v is String ? double.tryParse(v) : null);
int _int(dynamic v, [int fallback = 0]) => v is num ? v.toInt() : (int.tryParse('$v') ?? fallback);
int? _intN(dynamic v) => v is num ? v.toInt() : null;
bool? _boolN(dynamic v) => v is bool ? v : null;
List<String> _strs(dynamic v) => v is List ? v.map((e) => e.toString()).toList() : const [];
Json _obj(dynamic v) => v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
List<T> _list<T>(dynamic v, T Function(Json) f) =>
    v is List ? v.whereType<Map>().map((e) => f(Map<String, dynamic>.from(e))).toList() : <T>[];

// ---------------------------------------------------------------- catalog

class ProductSize {
  const ProductSize({required this.name, this.inStock});
  final String name;
  final bool? inStock;
  bool get available => inStock ?? true;

  factory ProductSize.fromJson(Json j) => ProductSize(name: _str(j['name']), inStock: _boolN(j['in_stock']));
}

class ProductImage {
  const ProductImage({required this.url, this.kind});
  final String url;
  final String? kind; // "product" (garment only) | "retailer_model"

  factory ProductImage.fromJson(Json j) => ProductImage(url: _str(j['url']), kind: _strN(j['kind']));
}

class Product {
  const Product({
    required this.id,
    required this.retailer,
    required this.name,
    required this.priceUsd,
    required this.imageUrl,
    this.brand,
    this.category,
    this.salePriceUsd,
    this.currency,
    this.colors = const [],
    this.sizes = const [],
    this.inStock,
    this.productUrl,
    this.images = const [],
    this.description,
    this.summary,
    this.label,
    this.styleTags = const [],
    this.pattern,
    this.formality,
    this.source,
  });

  final String id;
  final String retailer;
  final String name;
  final String? brand;
  final String? category;
  final double priceUsd;
  final double? salePriceUsd;
  final String? currency;
  final List<String> colors;
  final List<ProductSize> sizes;
  final bool? inStock;
  final String imageUrl;
  final String? productUrl;
  final List<ProductImage> images;
  final String? description;
  /// Card text from the server (1–2 sentences, ≤ 160 chars): Haiku's condensed description, or a
  /// one-liner from the attributes when the retailer has no text. Null until stage 2 has run.
  final String? summary;
  // AI tags (filled at ingest)
  final String? label;
  final List<String> styleTags;
  final String? pattern;
  final int? formality;
  final String? source;

  /// Price to charge: the sale price when it's set and lower.
  double get effectivePrice => (salePriceUsd != null && salePriceUsd! < priceUsd) ? salePriceUsd! : priceUsd;
  bool get isOnSale => effectivePrice < priceUsd;

  /// One readable line for a card. Prefers the server's [summary] (trimmed, whole); otherwise the
  /// first sentence of the retailer blurb, bullets and "- " markers stripped. Either way capped at
  /// [maxChars] on a word boundary. Null when there is neither.
  String? blurb({int maxChars = 110}) {
    final s = (summary ?? '').replaceAll(RegExp(r'\s+'), ' ').trim();
    if (s.isNotEmpty) return _cap(s, maxChars);
    final raw = (description ?? '').replaceAll(RegExp(r'[\r\n]+'), ' ').replaceAll(RegExp(r'\s*[-•·]\s+'), ' ').trim();
    if (raw.isEmpty) return null;
    final first = RegExp(r'^(.+?[.!?])(\s|$)').firstMatch(raw)?.group(1) ?? raw;
    return _cap(first.trim(), maxChars);
  }

  static String _cap(String out, int maxChars) {
    if (out.length > maxChars) {
      final cut = out.substring(0, maxChars);
      final space = cut.lastIndexOf(' ');
      out = '${(space > 40 ? cut.substring(0, space) : cut).trimRight()}…';
    }
    return out;
  }

  /// Gallery URLs (images[0] == image_url), falling back to the primary image.
  List<String> get gallery => images.isEmpty ? [imageUrl] : images.map((i) => i.url).toList();

  factory Product.fromJson(Json j) => Product(
        id: _str(j['id']),
        retailer: _str(j['retailer']),
        name: _str(j['name']),
        brand: _strN(j['brand']),
        category: _strN(j['category']),
        priceUsd: _dbl(j['price_usd']),
        salePriceUsd: _dblN(j['sale_price_usd']),
        currency: _strN(j['currency']),
        colors: _strs(j['colors']),
        sizes: _list(j['sizes'], ProductSize.fromJson),
        inStock: _boolN(j['in_stock']),
        imageUrl: _str(j['image_url']),
        productUrl: _strN(j['product_url']),
        images: _list(j['images'], ProductImage.fromJson),
        description: _strN(j['description']),
        summary: _strN(j['summary']),
        label: _strN(j['label']),
        styleTags: _strs(j['style_tags']),
        pattern: _strN(j['pattern']),
        formality: _intN(j['formality']),
        source: _strN(j['source']),
      );
}

/// A Product plus the AI ranking fields (feed cards, "shop this fit" results), from the same flat JSON.
class RankedProduct {
  const RankedProduct(
      {required this.product, this.reason, this.score, this.pairsWith = const [], this.matchedTag, this.yourSize,
      this.inYourSize, this.heroImageUrl, this.closetPicks = const [], this.tryOn});
  final Product product;
  final String? reason;
  final double? score;
  final List<String> pairsWith;
  final String? matchedTag; // shop-the-fit only

  /// Soft size ranking (council D3). [yourSize]: the size POST /size would pick from in-stock sizes (or,
  /// when that is sold out, the nearest size left), null when unknown. [inYourSize]: true = we have their
  /// real size; false = their size is sold out; null = we know nothing about their size or can't size this
  /// item (older servers too). Nothing is ever hidden for size.
  final String? yourSize;
  final bool? inYourSize;

  /// Sprint 4 §10.1 (reels Home). [heroImageUrl]: slide 1, the item on its own (null on older servers: use
  /// `product.imageUrl`). [closetPicks]: slide 3, the user's own pieces that go with it (0-4, one per
  /// square). [tryOn]: slide 2's state (null on older servers = treat as [TryOnState.none]).
  final String? heroImageUrl;
  final List<ClosetPick> closetPicks;
  final TryOnState? tryOn;

  String get id => product.id;

  factory RankedProduct.fromJson(Json j) => RankedProduct(
        product: Product.fromJson(j),
        reason: _strN(j['reason']),
        score: _dblN(j['score']),
        pairsWith: _strs(j['pairs_with']),
        matchedTag: _strN(j['matched_tag']),
        yourSize: _strN(j['your_size']),
        inYourSize: _boolN(j['in_your_size']),
        heroImageUrl: _strN(j['hero_image_url']),
        closetPicks: _list(j['closet_picks'], ClosetPick.fromJson),
        tryOn: j['tryon'] is Map ? TryOnState.fromJson(_obj(j['tryon'])) : null,
      );
}

/// Sprint 4 §10.1 `closet_picks[]`: one of the user's closet pieces shown on slide 3.
class ClosetPick {
  const ClosetPick({required this.id, required this.label, required this.category, this.imageUrl});
  final String id;
  final String label;
  final String category;
  final String? imageUrl;

  factory ClosetPick.fromJson(Json j) => ClosetPick(
      id: _str(j['id']), label: _str(j['label']), category: _str(j['category']), imageUrl: _strN(j['image_url']));
}

/// Sprint 4 §10.1 `tryon`: slide 2. [status] is one of ready | pending | none | needs_photo | unavailable
/// (unknown values read as none). [imageUrl] is set when ready, or the free collage when unavailable.
/// [mode]: "ai" | "collage".
class TryOnState {
  const TryOnState({required this.status, this.imageUrl, this.mode});
  static const none = TryOnState(status: 'none');
  static const _known = {'ready', 'pending', 'none', 'needs_photo', 'unavailable'};
  final String status;
  final String? imageUrl;
  final String? mode;

  bool get isReady => status == 'ready';
  bool get isPending => status == 'pending';
  bool get needsPhoto => status == 'needs_photo';
  bool get isUnavailable => status == 'unavailable';

  factory TryOnState.fromJson(Json j) {
    final st = _str(j['status'], 'none');
    return TryOnState(status: _known.contains(st) ? st : 'none', imageUrl: _strN(j['image_url']), mode: _strN(j['mode']));
  }
}

// ---------------------------------------------------------------- Discover (search)

/// GET /search/styles: one catalog style tag and how many items carry it.
class StyleTag {
  const StyleTag({required this.tag, required this.count});
  final String tag;
  final int count;

  factory StyleTag.fromJson(Json j) => StyleTag(tag: _str(j['tag']), count: _int(j['count']));
}

/// A trending product (GET /search/styles): users who saved + carted + ordered it. 0 = topped up from
/// the user's own feed when real traffic is thin.
class TrendingProduct {
  const TrendingProduct({required this.product, this.trendCount = 0});
  final Product product;
  final int trendCount;

  String get id => product.id;

  factory TrendingProduct.fromJson(Json j) =>
      TrendingProduct(product: Product.fromJson(j), trendCount: _int(j['trend_count']));
}

/// GET /search/styles?user_id=&limit= (Discover before a search, D11): style chips (most common first)
/// + a trending row.
class StyleChips {
  const StyleChips({this.styles = const [], this.trending = const []});
  final List<StyleTag> styles;
  final List<TrendingProduct> trending;

  factory StyleChips.fromJson(Json j) => StyleChips(
      styles: _list(j['styles'], StyleTag.fromJson), trending: _list(j['trending'], TrendingProduct.fromJson));
}

/// One "Goes with it" entry (GET /search, POST /search/photo): a catalog [product] (`from_closet: false`)
/// or one of the user's own [closetItem]s (`from_closet: true`; no price or retailer, can't go to the
/// cart or seeded Home), each with the engine's [reason].
class GoesWithItem {
  const GoesWithItem({this.product, this.closetItem, required this.fromCloset, this.reason = ''});
  final Product? product;
  final ClosetItem? closetItem;
  final bool fromCloset;
  final String reason;

  String get id => product?.id ?? closetItem?.id ?? '';
  String get label => product?.name ?? closetItem?.label ?? closetItem?.category ?? '';
  String get imageUrl => product?.imageUrl ?? closetItem?.imageUrl ?? '';

  factory GoesWithItem.fromJson(Json j) {
    // Closet items have no price/retailer; a stray entry without the flag is read by what it carries.
    final fromCloset = j['from_closet'] == true || (j['from_closet'] == null && j['price_usd'] == null && j['user_id'] != null);
    return GoesWithItem(
      product: fromCloset ? null : Product.fromJson(j),
      closetItem: fromCloset ? ClosetItem.fromJson(j) : null,
      fromCloset: fromCloset,
      reason: _str(j['reason']),
    );
  }
}

/// GET /search?user_id=&q= (D10): look-alikes of the query (in stock, one per style, up to 24) and
/// pieces that complete the look around `similar[0]`. A blank query gives empty lists; `goesWith` is
/// empty when the AI is down.
class SearchResult {
  const SearchResult({required this.query, this.similar = const [], this.goesWith = const []});
  final String query;
  final List<Product> similar;
  final List<GoesWithItem> goesWith;

  factory SearchResult.fromJson(Json j) => SearchResult(
        query: _str(j['query']),
        similar: _list(j['similar'], Product.fromJson),
        goesWith: _list(j['goes_with'], GoesWithItem.fromJson),
      );
}

/// POST /search/photo: the saved photo, the pieces the AI saw in it, catalog matches (with `reason`,
/// `score`, `matched_tag`, so [RankedProduct]) and what goes with the top match.
class PhotoSearchResult {
  const PhotoSearchResult({this.photoUrl = '', this.tags = const [], this.similar = const [], this.goesWith = const []});
  final String photoUrl;
  final List<FitTag> tags;
  final List<RankedProduct> similar;
  final List<GoesWithItem> goesWith;

  factory PhotoSearchResult.fromJson(Json j) => PhotoSearchResult(
        photoUrl: _str(j['photo_url']),
        tags: _list(j['tags'], FitTag.fromJson),
        similar: _list(j['similar'], RankedProduct.fromJson),
        goesWith: _list(j['goes_with'], GoesWithItem.fromJson),
      );
}

typedef FeedCard = RankedProduct;

// ---------------------------------------------------------------- save / swipe

class WishlistResult {
  const WishlistResult({required this.userId, required this.productId, required this.saved});
  final String userId;
  final String productId;
  final bool saved;

  factory WishlistResult.fromJson(Json j) =>
      WishlistResult(userId: _str(j['user_id']), productId: _str(j['product_id']), saved: j['saved'] == true);
}

class SwipeResult {
  const SwipeResult({required this.userId, required this.productId, required this.action, this.inCart});
  final String userId;
  final String productId;
  final String action;
  final bool? inCart;

  factory SwipeResult.fromJson(Json j) => SwipeResult(
      userId: _str(j['user_id']),
      productId: _str(j['product_id']),
      action: _str(j['action']),
      inCart: _boolN(j['in_cart']));
}

// ---------------------------------------------------------------- cart / checkout (Nabil)

class CartItem {
  const CartItem(
      {required this.productId, required this.size, required this.qty, this.addedAt, this.product, this.imageUrl});
  final String productId;
  final String size;
  final int qty;
  final String? addedAt;
  final Product? product;
  /// Thumbnail for the line (the flat `image_url` the server puts on every line): the product's image,
  /// still set when the product has left the catalog. Null only on older servers.
  final String? imageUrl;

  factory CartItem.fromJson(Json j) => CartItem(
        productId: _str(j['product_id']),
        size: _str(j['size']),
        qty: _int(j['qty'], 1),
        addedAt: _strN(j['added_at']),
        product: j['product'] is Map ? Product.fromJson(_obj(j['product'])) : null,
        imageUrl: _strN(j['image_url']),
      );
}

class CartGroup {
  const CartGroup({required this.retailer, required this.items, required this.subtotalUsd});
  final String retailer;
  final List<CartItem> items;
  final double subtotalUsd;

  factory CartGroup.fromJson(Json j) => CartGroup(
      retailer: _str(j['retailer']), items: _list(j['items'], CartItem.fromJson), subtotalUsd: _dbl(j['subtotal_usd']));
}

/// A cart line that can't be bought any more (GET /cart `unavailable`): not in [Cart.groups] or the totals,
/// but counted in [Cart.count]. Remove it with the usual DELETE. [reason]: "no longer available",
/// "size sold out" or "size no longer offered".
class UnavailableItem {
  const UnavailableItem(
      {required this.productId, required this.size, required this.qty, required this.name, this.product,
      required this.reason, this.imageUrl});
  final String productId;
  final String size;
  final int qty;
  final String name;
  final Product? product; // null when the product left the catalog
  final String reason;
  /// Thumbnail (flat `image_url` on the line): the image saved with the line when the product is gone
  /// ([product] null), so the row can still show a picture. Null on older servers / lines.
  final String? imageUrl;

  factory UnavailableItem.fromJson(Json j) => UnavailableItem(
        productId: _str(j['product_id']),
        size: _str(j['size']),
        qty: _int(j['qty'], 1),
        name: _str(j['name']),
        product: j['product'] is Map ? Product.fromJson(_obj(j['product'])) : null,
        reason: _str(j['unavailable_reason'], _str(j['reason'])),
        imageUrl: _strN(j['image_url']),
      );
}

class Cart {
  const Cart(
      {required this.userId, required this.groups, required this.totalUsd, required this.count,
      this.unavailable = const []});
  final String userId;
  final List<CartGroup> groups;
  final double totalUsd;
  final int count; // every line, unavailable ones included
  final List<UnavailableItem> unavailable; // empty on older servers

  factory Cart.fromJson(Json j) => Cart(
      userId: _str(j['user_id']),
      groups: _list(j['groups'], CartGroup.fromJson),
      totalUsd: _dbl(j['total_usd']),
      count: _int(j['count']),
      unavailable: _list(j['unavailable'], UnavailableItem.fromJson));
}

class PurchaseItem {
  const PurchaseItem({required this.productId, this.size, this.qty, this.priceUsd, this.name});
  final String productId;
  final String? size;
  final int? qty;
  final double? priceUsd;
  final String? name;

  factory PurchaseItem.fromJson(Json j) => PurchaseItem(
      productId: _str(j['product_id']),
      size: _strN(j['size']),
      qty: _intN(j['qty']),
      priceUsd: _dblN(j['price_usd']),
      name: _strN(j['name']));
}

class Purchase {
  const Purchase(
      {required this.retailer, required this.amountUsd, required this.items, required this.status, this.merchantId, this.nessieId});
  final String retailer;
  final String? merchantId;
  final double amountUsd;
  final List<PurchaseItem> items;
  final String status; // "paid" | "nessie_failed" | "pending_nessie"
  final String? nessieId;

  factory Purchase.fromJson(Json j) => Purchase(
        retailer: _str(j['retailer']),
        merchantId: _strN(j['merchant_id']),
        amountUsd: _dbl(j['amount_usd']),
        items: _list(j['items'], PurchaseItem.fromJson),
        status: _str(j['status']),
        nessieId: _strN(j['nessie_id']),
      );
}

class CheckoutResult {
  const CheckoutResult({required this.orderId, required this.purchases, required this.totalUsd, this.createdAt});
  final String orderId;
  final List<Purchase> purchases;
  final double totalUsd;
  final String? createdAt;

  factory CheckoutResult.fromJson(Json j) => CheckoutResult(
      orderId: _str(j['order_id']),
      purchases: _list(j['purchases'], Purchase.fromJson),
      totalUsd: _dbl(j['total_usd']),
      createdAt: _strN(j['created_at']));
}

class Order {
  const Order({required this.id, required this.purchases, required this.totalUsd, this.userId, this.createdAt});
  final String id;
  final String? userId;
  final List<Purchase> purchases;
  final double totalUsd;
  final String? createdAt;

  factory Order.fromJson(Json j) => Order(
      id: _str(j['id']),
      userId: _strN(j['user_id']),
      purchases: _list(j['purchases'], Purchase.fromJson),
      totalUsd: _dbl(j['total_usd']),
      createdAt: _strN(j['created_at']));
}

// ---------------------------------------------------------------- AI (Adam)

class SizeAdvice {
  const SizeAdvice({this.size, required this.confidence, required this.reason});
  final String? size;
  final String confidence; // "high" | "medium" | "low"
  final String reason;

  factory SizeAdvice.fromJson(Json j) =>
      SizeAdvice(size: _strN(j['size']), confidence: _str(j['confidence'], 'low'), reason: _str(j['reason']));
}

class TryOnResponse {
  const TryOnResponse({required this.imageUrl, required this.cached, this.mode, this.sourcePhotoUrl});
  final String imageUrl;
  final bool cached;
  final String? mode; // "ai" = real try-on, "collage" = outfit board

  /// The user's own photo the try-on was edited from (their body photo or one of their outfit photos
  /// that shows the garment being replaced); null on older servers or when the user has no photo.
  /// Handy for a before/after toggle.
  final String? sourcePhotoUrl;

  bool get isOutfitBoard => mode == 'collage';

  factory TryOnResponse.fromJson(Json j) => TryOnResponse(
      imageUrl: _str(j['image_url']),
      cached: j['cached'] == true,
      mode: _strN(j['mode']),
      sourcePhotoUrl: _strN(j['source_photo_url']));
}

class LookItem {
  const LookItem({required this.source, required this.category, required this.label, this.id, this.reason});
  final String source; // "closet" | "catalog"
  final String? id;
  final String category;
  final String label;
  final String? reason;

  factory LookItem.fromJson(Json j) => LookItem(
      source: _str(j['source']),
      id: _strN(j['id']),
      category: _str(j['category']),
      label: _str(j['label']),
      reason: _strN(j['reason']));
}

class CompleteLook {
  const CompleteLook(
      {required this.items,
      required this.newItemsTotalUsd,
      required this.missing,
      this.anchorId,
      this.score,
      this.fitScore,
      this.primaryStyle});
  final String? anchorId;
  final List<LookItem> items;
  final double newItemsTotalUsd;
  final List<String> missing;
  final double? score;

  /// Fit Score v2 of the completed outfit (anchor + picks), said as the anchor's style. Null on an old server.
  final FitScore? fitScore;

  /// The style the look was completed in (the anchor's best style), e.g. 'athleisure'.
  final String? primaryStyle;

  factory CompleteLook.fromJson(Json j) => CompleteLook(
        anchorId: _strN(j['anchor_id']),
        items: _list(j['items'], LookItem.fromJson),
        newItemsTotalUsd: _dbl(j['new_items_total_usd']),
        missing: _strs(j['missing']),
        score: _dblN(j['score']),
        fitScore: j['fit_score'] is Map ? FitScore.fromJson(_obj(j['fit_score'])) : null,
        primaryStyle: _strN(j['primary_style']),
      );
}

class FitScoreBreakdown {
  const FitScoreBreakdown(
      {required this.color, required this.pattern, required this.formality, required this.completeness});
  final int color;
  final int pattern;
  final int formality;
  final int completeness;

  factory FitScoreBreakdown.fromJson(Json j) => FitScoreBreakdown(
      color: _int(j['color']),
      pattern: _int(j['pattern']),
      formality: _int(j['formality']),
      completeness: _int(j['completeness']));
}

/// One Fit Score v2 criterion, 0-10 (5 = fine, 8+ earned): color, silhouette, pattern, formality, style,
/// completeness, layering, occasion (only when an occasion was sent).
class FitCriterion {
  const FitCriterion({required this.name, required this.score10, this.note});
  final String name;
  final int score10;
  final String? note;

  factory FitCriterion.fromJson(Json j) =>
      FitCriterion(name: _str(j['name']), score10: _int(j['score_10']), note: _strN(j['note']));
}

class FitScore {
  const FitScore({
    required this.score,
    required this.verdict,
    required this.notes,
    required this.breakdown,
    this.criteria = const [],
    this.styleScores = const {},
    this.primaryStyle,
    this.rawScore,
    this.source,
  });
  final int score;

  /// v2: "68 as streetwear: strong silhouette, palette too busy".
  final String verdict;
  final List<String> notes;
  final FitScoreBreakdown breakdown;

  /// v2 per-criterion scores (empty on an old server).
  final List<FitCriterion> criteria;

  /// v2: how well the outfit executes each style, 0-100 (streetwear, minimalist, classic, y2k, preppy,
  /// athleisure, vintage, business, boho, grunge). Empty on an old server.
  final Map<String, int> styleScores;

  /// v2: the style the headline score is said in ("68 · as streetwear"); null on an old server.
  final String? primaryStyle;
  final int? rawScore;

  /// 'rules' or 'rules+ai' (photo critic blended in).
  final String? source;

  factory FitScore.fromJson(Json j) => FitScore(
      score: _int(j['score']),
      verdict: _str(j['verdict']),
      notes: _strs(j['notes']),
      breakdown: FitScoreBreakdown.fromJson(_obj(j['breakdown'])),
      criteria: _list(j['criteria'], FitCriterion.fromJson),
      styleScores: {for (final e in _obj(j['style_scores']).entries) e.key: _int(e.value)},
      primaryStyle: _strN(j['primary_style']),
      rawScore: _intN(j['raw_score']),
      source: _strN(j['source']));
}

class StyleShare {
  const StyleShare({required this.tag, required this.share});
  final String tag;
  final double share;

  factory StyleShare.fromJson(Json j) => StyleShare(tag: _str(j['tag']), share: _dbl(j['share']));
}

class PaletteColor {
  const PaletteColor({required this.name, required this.family, required this.hex, required this.share});
  final String name;
  final String family;
  final String hex;
  final double share;

  factory PaletteColor.fromJson(Json j) =>
      PaletteColor(name: _str(j['name']), family: _str(j['family']), hex: _str(j['hex'], '#9E9E9E'), share: _dbl(j['share']));
}

class RetailerShare {
  const RetailerShare({required this.retailer, required this.share});
  final String retailer;
  final double share;

  factory RetailerShare.fromJson(Json j) => RetailerShare(retailer: _str(j['retailer']), share: _dbl(j['share']));
}

/// GET /users/{id}/style ("Your Style DNA").
class StyleProfile {
  const StyleProfile({
    required this.headline,
    required this.styles,
    required this.palette,
    required this.patterns,
    required this.formalityAvg,
    required this.formalityLabel,
    required this.priceRanges,
    required this.favoriteRetailers,
    required this.avoid,
    required this.sampleSize,
    required this.confidence,
  });

  final String headline;
  final List<StyleShare> styles;
  final List<PaletteColor> palette;
  final Map<String, double> patterns;
  final double? formalityAvg;
  final String formalityLabel;
  final Map<String, List<double>> priceRanges; // category -> [low, high]
  final List<RetailerShare> favoriteRetailers;
  final List<String> avoid;
  final Map<String, int> sampleSize; // liked / discarded / closet
  final String confidence;

  factory StyleProfile.fromJson(Json j) {
    final formality = _obj(j['formality']);
    return StyleProfile(
      headline: _str(j['headline']),
      styles: _list(j['styles'], StyleShare.fromJson),
      palette: _list(j['palette'], PaletteColor.fromJson),
      patterns: _obj(j['patterns']).map((k, v) => MapEntry(k, _dbl(v))),
      formalityAvg: _dblN(formality['avg']),
      formalityLabel: _str(formality['label'], 'unknown'),
      priceRanges: _obj(j['price_ranges'])
          .map((k, v) => MapEntry(k, v is List ? v.map((e) => _dbl(e)).toList() : <double>[])),
      favoriteRetailers: _list(j['favorite_retailers'], RetailerShare.fromJson),
      avoid: _strs(j['avoid']),
      sampleSize: _obj(j['sample_size']).map((k, v) => MapEntry(k, _int(v))),
      confidence: _str(j['confidence'], 'low'),
    );
  }
}

Map<String, List<double>> _ranges(dynamic v) =>
    _obj(v).map((k, r) => MapEntry(k, r is List ? r.map((e) => _dbl(e)).toList() : <double>[]));

/// GET /products (search + paging).
class ProductPage {
  const ProductPage({required this.items, required this.total, required this.limit, required this.offset,
      this.nextOffset});

  final List<Product> items;
  final int total;
  final int limit;
  final int offset;
  final int? nextOffset; // null on the last page

  factory ProductPage.fromJson(Json j) => ProductPage(
        items: _list(j['items'], Product.fromJson),
        total: _int(j['total']),
        limit: _int(j['limit']),
        offset: _int(j['offset']),
        nextOffset: _intN(j['next_offset']),
      );
}

/// A user (backend `User`): /users, /users/{id}, /onboarding, /style/apply.
class AppUser {
  const AppUser({required this.id, required this.displayName, this.styleText = '', this.priceRanges = const {},
      this.bodyPhotoUrl, this.friends = const [], this.bodyProfile, this.preferredStores = const [],
      this.onboarded = false, this.shopFor = 'both', this.styleTags = const []});

  final String id;
  final String displayName;
  final String styleText;
  final List<String> styleTags; // inferred by POST /onboarding/photos; empty for users who typed their style
  final Map<String, List<double>> priceRanges; // category -> [min, max]
  final String? bodyPhotoUrl;
  final List<String> friends;
  final BodyProfile? bodyProfile; // null until the user does a body scan
  final List<String> preferredStores; // retailer ids ("hm", "uniqlo"); the feed boosts them (D5)
  final bool onboarded; // set by the app at the end of onboarding (D6, screen 7)
  final String shopFor; // men | women | both (default): the feed and Discover filter by it

  factory AppUser.fromJson(Json j) => AppUser(
        id: _str(j['id']),
        displayName: _str(j['display_name']),
        styleText: _str(j['style_text']),
        styleTags: _strs(j['style_tags']),
        priceRanges: _ranges(j['price_ranges']),
        bodyPhotoUrl: _strN(j['body_photo_url']),
        friends: _strs(j['friends']),
        bodyProfile: j['body_profile'] is Map ? BodyProfile.fromJson(_obj(j['body_profile'])) : null,
        preferredStores: _strs(j['preferred_stores']),
        onboarded: j['onboarded'] == true,
        shopFor: _str(j['shop_for']).isEmpty ? 'both' : _str(j['shop_for']),
      );
}

/// The user's body profile (lengths in inches): typed via PATCH /users/{id}/body-profile and/or estimated
/// by POST /users/{id}/body-scan. Any number may be null. [source]: "manual" (typed), "ai" (read from the
/// photo) or "estimate" (height/weight formula). [manual] lists the fields the user typed.
class BodyProfile {
  const BodyProfile({required this.heightCm, this.weightKg, this.chestIn, this.waistIn, this.hipIn, this.inseamIn,
      this.build, required this.source, this.fullBody, this.note = '', this.scannedAt, this.shoeUs, this.fit,
      this.usualSizes = const {}, this.manual = const [], this.scanPhotos = 0, this.confidence});

  final double heightCm;
  final double? weightKg;
  final double? chestIn;
  final double? waistIn;
  final double? hipIn;
  final double? inseamIn;
  final String? build; // slim | average | athletic | curvy | broad
  final String source;
  final bool? fullBody; // false: the photo wasn't one standing person head to feet
  final String note; // short fit tip, or a hint to retake the photo
  final String? scannedAt;
  final double? shoeUs;
  final String? fit; // slim | regular | oversized
  final Map<String, String> usualSizes; // category -> usual size
  final List<String> manual;
  final int scanPhotos; // full-body photos averaged by the last scan (0: formula / typed only)
  final String? confidence; // low | medium | high for 1 / 2 / 3+ full-body photos; null on older servers

  factory BodyProfile.fromJson(Json j) => BodyProfile(
        heightCm: _dbl(j['height_cm']),
        weightKg: _dblN(j['weight_kg']),
        chestIn: _dblN(j['chest_in']),
        waistIn: _dblN(j['waist_in']),
        hipIn: _dblN(j['hip_in']),
        inseamIn: _dblN(j['inseam_in']),
        build: _strN(j['build']),
        source: _str(j['source'], 'estimate'),
        fullBody: _boolN(j['full_body']),
        note: _str(j['note']),
        scannedAt: _strN(j['scanned_at']),
        shoeUs: _dblN(j['shoe_us']),
        fit: _strN(j['fit']),
        usualSizes: {for (final e in _obj(j['usual_sizes']).entries) e.key: _str(e.value)},
        manual: _strs(j['manual']),
        scanPhotos: _int(j['scan_photos']),
        confidence: _strN(j['confidence']),
      );

  /// The server's snake_case shape (what `fromJson` read), for sending a reviewed profile back
  /// (`Api.confirmBodyScan`). Nulls are kept so a cleared field stays cleared.
  Json toJson() => {
        'height_cm': heightCm, 'weight_kg': weightKg, 'chest_in': chestIn, 'waist_in': waistIn, 'hip_in': hipIn,
        'inseam_in': inseamIn, 'build': build, 'source': source, 'full_body': fullBody, 'note': note,
        'scanned_at': scannedAt, 'shoe_us': shoeUs, 'fit': fit, 'usual_sizes': usualSizes, 'manual': manual,
        'scan_photos': scanPhotos, if (confidence != null) 'confidence': confidence,
      };
}

/// POST /ai/vibe: what a Discover search sentence means, as catalog filters.
class VibeQuery {
  const VibeQuery(
      {this.styles = const [], this.categories = const [], this.colors = const [], this.keywords = const [],
      this.source = 'rules'});

  final List<String> styles; // y2k | streetwear | minimalist | preppy | athleisure | vintage | business | boho | grunge | classic
  final List<String> categories; // top | bottom | outerwear | shoes | dress | accessory
  final List<String> colors;
  final List<String> keywords; // short item words, e.g. "satin shirt"
  final String source; // ai | rules

  bool get isEmpty => styles.isEmpty && categories.isEmpty && colors.isEmpty && keywords.isEmpty;

  factory VibeQuery.fromJson(Json j) => VibeQuery(
        styles: _strs(j['styles']),
        categories: _strs(j['categories']),
        colors: _strs(j['colors']),
        keywords: _strs(j['keywords']),
        source: _str(j['source'], 'rules'),
      );
}

/// POST /users/{id}/body-scan (and /body-scan/confirm).
class BodyScanResult {
  const BodyScanResult({required this.bodyPhotoUrl, required this.profile, this.committed = true, this.skipped = 0});

  final String bodyPhotoUrl; // the first full-body photo (try-on photo), or the only photo if none was
  final BodyProfile profile;
  final int skipped; // photos ignored because they weren't one standing person head to feet
  /// False for a draft (`bodyScan(commit: false)`): nothing is saved on the user until
  /// `Api.confirmBodyScan(draft, ...)`. True (also on older servers) when the scan was saved.
  final bool committed;

  factory BodyScanResult.fromJson(Json j) => BodyScanResult(
      bodyPhotoUrl: _str(j['body_photo_url']),
      profile: BodyProfile.fromJson(_obj(j['body_profile'])),
      committed: j['committed'] != false,
      skipped: _int(j['skipped']));
}

/// POST /onboarding: the saved user plus what the rules parser understood.
class OnboardingResult {
  const OnboardingResult({required this.user, required this.styles, required this.budgets, required this.unmatched});

  final AppUser user;
  final List<String> styles; // style tags found in the text
  final Map<String, List<double>> budgets; // category -> [min, max] found in the text
  final String unmatched; // words it didn't understand

  factory OnboardingResult.fromJson(Json j) {
    final parsed = _obj(j['parsed']);
    return OnboardingResult(
      user: AppUser.fromJson(_obj(j['user'])),
      styles: _strs(parsed['styles']),
      budgets: _ranges(parsed['budgets']),
      unmatched: _str(parsed['unmatched']),
    );
  }
}

/// POST /onboarding/photos: a batch of photos -> closet digitized, body scanned, style inferred.
class PhotoOnboardingResult {
  const PhotoOnboardingResult({
    required this.closetAdded,
    required this.skippedDuplicates,
    this.bodyProfile,
    this.bodyPhotoUrl,
    required this.styleText,
    required this.styleTags,
    required this.colors,
    required this.formality,
    required this.shopFor,
    required this.user,
  });

  final List<ClosetItem> closetAdded; // new garments (duplicates of the closet or each other are skipped)
  final int skippedDuplicates;
  final BodyProfile? bodyProfile; // estimates from the best full-body photo, or the height/weight formula
  final String? bodyPhotoUrl; // the full-body photo now used for try-on; null if none was full-body
  final String styleText; // "streetwear and minimalist; grey hoodie, light wash jeans; mostly casual"
  final List<String> styleTags; // top tags by frequency (style_hint tags first)
  final List<String> colors; // dominant colors
  final String formality; // loungewear | casual | smart casual | dressy | formal | unknown
  final String shopFor; // men | women | both: set from the full-body photo when the user never chose
  final AppUser user; // saved user: style_text set, onboarded = true

  factory PhotoOnboardingResult.fromJson(Json j) {
    final style = _obj(j['style']);
    return PhotoOnboardingResult(
      closetAdded: _list(j['closet_added'], ClosetItem.fromJson),
      skippedDuplicates: _int(j['closet_skipped_duplicates']),
      bodyProfile: j['body_profile'] is Map ? BodyProfile.fromJson(_obj(j['body_profile'])) : null,
      bodyPhotoUrl: _strN(j['body_photo_url']),
      styleText: _str(style['style_text']),
      styleTags: _strs(style['style_tags']),
      colors: _strs(style['colors']),
      formality: _str(style['formality'], 'unknown'),
      shopFor: _str(j['shop_for'], 'both'),
      user: AppUser.fromJson(_obj(j['user'])),
    );
  }
}

/// POST /users/{id}/style/apply.
class StyleApplyResult {
  const StyleApplyResult({required this.user, required this.profile});

  final AppUser user;
  final StyleProfile profile;

  factory StyleApplyResult.fromJson(Json j) =>
      StyleApplyResult(user: AppUser.fromJson(_obj(j['user'])), profile: StyleProfile.fromJson(_obj(j['profile'])));
}

// ---------------------------------------------------------------- closet

class ClosetItem {
  const ClosetItem({
    required this.id,
    required this.userId,
    required this.imageUrl,
    required this.category,
    required this.color,
    this.pattern,
    this.styleTags = const [],
    this.formality,
    this.source,
    this.label,
    this.duplicateOf,
    this.brand,
    this.productId,
    this.catalogImageUrl,
    this.matchConfidence,
    this.displayImageUrl,
    this.cropImageUrl,
    this.wornIn = const [],
    this.outfitId,
    this.cleanSourcePhotoUrl,
    this.cleanSourceBox,
  });

  final String id;
  final String userId;
  /// Same as [displayImageUrl] on closet v2 items (kept for older screens).
  final String imageUrl;
  final String category;
  final String color;
  final String? pattern;
  final List<String> styleTags;
  final int? formality;
  final String? source;
  final String? label;
  final String? duplicateOf; // set on upload when it looks like something already in the closet
  // ---- closet v2 (Oct 24): the piece on its own, plus the fits it was worn in
  final String? brand; // read off a visible logo/label, or from the catalog match; null = unknown
  final String? productId; // catalog product this piece was matched to (confident match only)
  final String? catalogImageUrl;
  final double? matchConfidence; // 0-1, with productId
  /// What the closet grid shows: a generated clean shot of the user's own crop, else the crop. Never the
  /// catalog photo (sprint-3 §1.2): [catalogImageUrl] is only for "shop similar".
  final String? displayImageUrl;
  /// The garment cropped out of the photo it was found in (the whole photo when there was no box).
  final String? cropImageUrl;
  /// Outfit photos this piece appeared in (closet uploads and Fit Check posts), oldest first.
  final List<WornIn> wornIn;
  // ---- sprint-3 §1 (Oct 24, night)
  /// The [ClosetOutfit] this piece was first digitized from; null for a single-piece upload or a piece
  /// whose outfit was deleted.
  final String? outfitId;
  /// The source photo the clean shot was generated from (the best of [wornIn]) and the garment's box in it.
  final String? cleanSourcePhotoUrl;
  final List<double>? cleanSourceBox;

  /// [displayImageUrl] when present, else [imageUrl]: always something to render.
  String get shownImageUrl => displayImageUrl ?? imageUrl;

  factory ClosetItem.fromJson(Json j) => ClosetItem(
        id: _str(j['id']),
        userId: _str(j['user_id']),
        imageUrl: _str(j['image_url']),
        category: _str(j['category']),
        color: _str(j['color']),
        pattern: _strN(j['pattern']),
        styleTags: _strs(j['style_tags']),
        formality: _intN(j['formality']),
        source: _strN(j['source']),
        label: _strN(j['label']),
        duplicateOf: _strN(j['duplicate_of']),
        brand: _strN(j['brand']),
        productId: _strN(j['product_id']),
        catalogImageUrl: _strN(j['catalog_image_url']),
        matchConfidence: _dblN(j['match_confidence']),
        displayImageUrl: _strN(j['display_image_url']),
        cropImageUrl: _strN(j['crop_image_url']),
        wornIn: _list(j['worn_in'], WornIn.fromJson),
        outfitId: _strN(j['outfit_id']),
        cleanSourcePhotoUrl: _strN(j['clean_source_photo_url']),
        cleanSourceBox: FitTag._box(j['clean_source_box']),
      );
}

/// One outfit photo a closet piece was worn in. `source` is `closet` (an outfit upload) or `fitcheck`
/// (a Fit Check post). `at` is an ISO-8601 UTC string. [box] is where the piece sits in that photo
/// ([xMin, yMin, xMax, yMax] as 0-1 fractions), null on old entries or when it wasn't boxed.
class WornIn {
  const WornIn({required this.photoUrl, this.at, this.source, this.box});
  final String photoUrl;
  final String? at;
  final String? source;
  final List<double>? box;
  DateTime? get time => at == null ? null : DateTime.tryParse(at!);
  factory WornIn.fromJson(Json j) =>
      WornIn(photoUrl: _str(j['photo_url']), at: _strN(j['at']), source: _strN(j['source']), box: FitTag._box(j['box']));
}

/// `GET /closet/{user}/outfits` entry (sprint-3 §1.3): one whole-fit photo the user uploaded (`source`
/// `closet`) or posted to Fit Check (`fitcheck`), with the pieces digitized from it. Deleting an outfit
/// ([Api.deleteClosetOutfit]) keeps its pieces in the closet.
class ClosetOutfit {
  const ClosetOutfit({
    required this.id,
    required this.photoUrl,
    this.createdAt,
    this.source,
    this.pieceIds = const [],
    this.pieces = const [],
    this.posted = false,
  });
  final String id;
  final String photoUrl;
  /// The same photo is also an Inspo post (one outfit either way).
  final bool posted;
  final String? createdAt; // ISO-8601 UTC
  final String? source; // 'closet' | 'fitcheck'
  final List<String> pieceIds;
  /// The pieces that still exist, in detection order.
  final List<ClosetItem> pieces;
  DateTime? get time => createdAt == null ? null : DateTime.tryParse(createdAt!);
  factory ClosetOutfit.fromJson(Json j) => ClosetOutfit(
        id: _str(j['id']),
        photoUrl: _str(j['photo_url']),
        createdAt: _strN(j['created_at']),
        source: _strN(j['source']),
        pieceIds: _strs(j['piece_ids']),
        pieces: _list(j['pieces'], ClosetItem.fromJson),
        posted: j['posted'] == true || j['source'] == 'fitcheck',
      );
}

/// `POST /closet/upload` result: new pieces, existing pieces a photo matched (the photo was added to
/// their [ClosetItem.wornIn] instead of making a twin), and photos that weren't clothing.
class ClosetUploadResult {
  const ClosetUploadResult({required this.added, required this.merged, required this.skipped, this.outfits = const []});
  final List<ClosetItem> added;
  final List<ClosetItem> merged;
  final int skipped;
  /// One [ClosetOutfit] per outfit photo (kind `outfit`) that had at least one garment; empty for pieces.
  final List<ClosetOutfit> outfits;
  List<ClosetItem> get all => [...added, ...merged];
  factory ClosetUploadResult.fromJson(Json j) => ClosetUploadResult(
        added: _list(j['added'], ClosetItem.fromJson),
        merged: _list(j['merged'], ClosetItem.fromJson),
        skipped: _int(j['skipped']),
        outfits: _list(j['outfits'], ClosetOutfit.fromJson),
      );
}

// ---------------------------------------------------------------- Fit Check (Nabil's routes, Adam's tagging)

class FitTag {
  const FitTag({
    required this.label,
    this.retailer,
    this.productId,
    this.closetItemId,
    this.category,
    this.color,
    this.pattern,
    this.styleTags = const [],
    this.brand,
    this.box,
  });

  final String label;
  final String? retailer;
  final String? productId;
  final String? closetItemId;
  final String? category;
  final String? color;
  final String? pattern;
  final List<String> styleTags;
  final String? brand;

  /// Where the item sits in the post photo, for Inspo pins: [xMin, yMin, xMax, yMax] as 0-1 fractions
  /// of the image width/height (pin at the center: ((x0+x1)/2, (y0+y1)/2)). Null on old posts and
  /// hand-added tags.
  final List<double>? box;

  factory FitTag.fromJson(Json j) => FitTag(
        label: _str(j['label']),
        retailer: _strN(j['retailer']),
        productId: _strN(j['product_id']),
        closetItemId: _strN(j['closet_item_id']),
        category: _strN(j['category']),
        color: _strN(j['color']),
        pattern: _strN(j['pattern']),
        styleTags: _strs(j['style_tags']),
        brand: _strN(j['brand']),
        box: _box(j['box']),
      );

  static List<double>? _box(dynamic v) {
    if (v is! List || v.length != 4 || v.any((e) => e is! num)) return null;
    final b = [for (final e in v) (e as num).toDouble()];
    return b[0] < b[2] && b[1] < b[3] && b.every((e) => e >= 0 && e <= 1) ? b : null;
  }

  Json toJson() => {
        'label': label,
        if (retailer != null) 'retailer': retailer,
        if (productId != null) 'product_id': productId,
        if (closetItemId != null) 'closet_item_id': closetItemId,
        if (category != null) 'category': category,
        if (color != null) 'color': color,
        if (pattern != null) 'pattern': pattern,
        'style_tags': styleTags,
        if (brand != null) 'brand': brand,
        if (box != null) 'box': box,
      };
}

/// One tagged piece of a Fit Check post with its own similar items (`GET /fitcheck/{id}/shop?grouped=true`).
/// Groups come back in post (tag) order; a piece with no match yet has an empty [products] so its chip /
/// pin can still be shown. [tag] carries only label, category, color, box and productId.
class ShopTagGroup {
  const ShopTagGroup({required this.tag, this.products = const []});
  final FitTag tag;
  final List<RankedProduct> products; // up to 6, closest match first

  bool get isEmpty => products.isEmpty;

  factory ShopTagGroup.fromJson(Json j) =>
      ShopTagGroup(tag: FitTag.fromJson(_obj(j['tag'])), products: _list(j['products'], RankedProduct.fromJson));
}

class FitCheckComment {
  const FitCheckComment(
      {required this.id, required this.userId, required this.text, this.createdAt, this.commentCount, String? authorName})
      : _authorName = authorName;
  final String id;
  final String userId;
  final String text;
  final String? createdAt;
  final int? commentCount; // only on the POST .../comments response
  final String? _authorName;

  /// The commenter's display name (`author.display_name`); the user id when the server sent no author
  /// (comments embedded in a post from an older server).
  String get authorName => _authorName ?? userId;

  factory FitCheckComment.fromJson(Json j) {
    final author = _obj(j['author']);
    return FitCheckComment(
        id: _str(j['id']),
        userId: _str(j['user_id']),
        text: _str(j['text']),
        createdAt: _strN(j['created_at']),
        commentCount: _intN(j['comment_count']),
        authorName: _strN(author['display_name'] ?? author['id']));
  }
}

/// One page of a post's comments (`GET /fitcheck/{id}/comments`), oldest -> newest. [nextBefore] is the
/// cursor (a comment id) for the next, older page; null when there is nothing older.
class FitCheckCommentsPage {
  const FitCheckCommentsPage({required this.postId, this.commentCount, this.comments = const [], this.nextBefore});
  final String postId;
  final int? commentCount; // total on the post
  final List<FitCheckComment> comments;
  final String? nextBefore;

  bool get hasMore => nextBefore != null;

  factory FitCheckCommentsPage.fromJson(Json j) => FitCheckCommentsPage(
      postId: _str(j['post_id']),
      commentCount: _intN(j['comment_count']),
      comments: _list(j['comments'], FitCheckComment.fromJson),
      nextBefore: _strN(j['next_before']));
}

class FitCheckPost {
  const FitCheckPost({
    required this.id,
    required this.userId,
    required this.photoUrl,
    this.caption,
    this.tagged = const [],
    this.createdAt,
    this.likes = const [],
    this.comments = const [],
    this.visibility,
    this.authorName,
    this.likeCount,
    this.likedByMe,
    this.commentCount,
    this.photoWidth,
    this.photoHeight,
    this.reactions = const {},
    this.myReaction,
  });

  final String id;
  final String userId;
  final String photoUrl;

  /// Emoji reactions (Oct 25): count per emoji, only emojis with at least one ([fitCheckReactions] order),
  /// and the viewer's own (null = none). An old-style like counts as 😍.
  final Map<String, int> reactions;
  final String? myReaction;
  int get reactionTotal => reactions.values.fold(0, (a, b) => a + b);
  final String? caption;
  final List<FitTag> tagged;
  final String? createdAt;
  final List<String> likes;
  final List<FitCheckComment> comments;
  final String? visibility;
  final String? authorName;
  final int? likeCount;
  final bool? likedByMe;
  final int? commentCount;

  /// Pixel size of the photo (`photo_w` / `photo_h`): measured by the server for uploads, the size the app
  /// sent for external URLs. Both null on posts from before the fields existed (lay the photo out at its
  /// own ratio, sprint-3 3.1). [photoAspectRatio] = width / height, null when unknown or invalid.
  final int? photoWidth;
  final int? photoHeight;
  double? get photoAspectRatio =>
      photoWidth != null && photoHeight != null && photoWidth! > 0 && photoHeight! > 0 ? photoWidth! / photoHeight! : null;

  factory FitCheckPost.fromJson(Json j) {
    final author = _obj(j['author']);
    return FitCheckPost(
      id: _str(j['id']),
      userId: _str(j['user_id']),
      photoUrl: _str(j['photo_url']),
      caption: _strN(j['caption']),
      tagged: _list(j['tagged'], FitTag.fromJson),
      createdAt: _strN(j['created_at']),
      likes: _strs(j['likes']),
      comments: _list(j['comments'], FitCheckComment.fromJson),
      visibility: _strN(j['visibility']),
      authorName: _strN(author['display_name'] ?? author['id']),
      likeCount: _intN(j['like_count']),
      likedByMe: _boolN(j['liked_by_me']),
      commentCount: _intN(j['comment_count']),
      photoWidth: _intN(j['photo_w']),
      photoHeight: _intN(j['photo_h']),
      reactions: _reactionCounts(j['reactions']),
      myReaction: _strN(j['my_reaction']),
    );
  }
}

/// The emoji set the server accepts for PUT /fitcheck/{id}/reaction, in display order.
const fitCheckReactions = ['🔥', '😍', '👀', '💯'];

Map<String, int> _reactionCounts(dynamic v) {
  final m = _obj(v);
  return {
    for (final e in fitCheckReactions)
      if (_int(m[e]) > 0) e: _int(m[e])
  };
}

/// PUT /fitcheck/{id}/reaction result.
class ReactionResult {
  const ReactionResult({required this.postId, this.reactions = const {}, this.myReaction});
  final String postId;
  final Map<String, int> reactions;
  final String? myReaction;
  factory ReactionResult.fromJson(Json j) => ReactionResult(
      postId: _str(j['post_id']), reactions: _reactionCounts(j['reactions']), myReaction: _strN(j['my_reaction']));
}

/// GET /fitcheck/{id}/similar: one tagged piece of a post, the viewer's own similar [closet] pieces first,
/// then [products] to buy (up to 6, closest first).
class SimilarLookGroup {
  const SimilarLookGroup({required this.tag, this.closet = const [], this.products = const []});
  final FitTag tag;
  final List<ClosetItem> closet;
  final List<RankedProduct> products;
  factory SimilarLookGroup.fromJson(Json j) => SimilarLookGroup(
      tag: FitTag.fromJson(_obj(j['tag'])),
      closet: _list(j['closet'], ClosetItem.fromJson),
      products: _list(j['products'], RankedProduct.fromJson));
}

/// One retailer we carry (`GET /stores`): [count] in-stock products, [departments] in-stock products per
/// `men` / `women` / `unisex`. [Api.stores] fills the name cache behind [StoreInfo.nameFor].
class StoreInfo {
  const StoreInfo({required this.id, required this.name, this.count = 0, this.departments = const {}});
  final String id;
  final String name;
  final int count;
  final Map<String, int> departments;

  factory StoreInfo.fromJson(Json j) {
    final id = _str(j['id']);
    return StoreInfo(
        id: id,
        name: _str(j['name'], id),
        count: _int(j['count']),
        departments: {for (final e in _obj(j['departments']).entries) e.key: _int(e.value)});
  }

  static final Map<String, String> _names = {};

  /// Server names learned from the last [Api.stores] call (`[StoreInfo.remember]`); the id itself before
  /// that or for a retailer the server never listed. Pure: no network, safe to call from `build`.
  static String nameFor(String id) => _names[id] ?? id;

  /// Whether [nameFor] knows a server name for [id].
  static bool knows(String id) => _names.containsKey(id);

  /// Replaces the name cache with [stores] (called by [Api.stores]).
  static void remember(Iterable<StoreInfo> stores) {
    _names
      ..clear()
      ..addEntries(stores.where((s) => s.id.isNotEmpty).map((s) => MapEntry(s.id, s.name)));
  }
}

class LikeResult {
  const LikeResult({required this.postId, required this.liked, required this.likeCount});
  final String postId;
  final bool liked;
  final int likeCount;

  factory LikeResult.fromJson(Json j) =>
      LikeResult(postId: _str(j['post_id']), liked: j['liked'] == true, likeCount: _int(j['like_count']));
}

class ClosetDeleteResult {
  const ClosetDeleteResult(this.deleted);
  final String deleted;
  factory ClosetDeleteResult.fromJson(Json j) => ClosetDeleteResult(_str(j['deleted']));
}

// ---------------------------------------------------------------- AI Fit Creator (Adam)

/// One slot of an [OutfitFit]: either something the user owns ([closetItem]) or a catalog [product] in
/// [yourSize]. `slot` is top | bottom | shoes | outerwear | dress | accessory.
class FitPiece {
  const FitPiece({required this.slot, required this.source, this.closetItem, this.product, this.yourSize, this.inYourSize});
  final String slot;
  final String source; // "closet" | "catalog"
  final ClosetItem? closetItem;
  final Product? product;
  final String? yourSize;
  final bool? inYourSize;

  bool get fromCloset => source == 'closet';
  String get imageUrl => closetItem?.imageUrl ?? product?.imageUrl ?? '';
  String get label => closetItem?.label ?? closetItem?.category ?? product?.name ?? slot;

  factory FitPiece.fromJson(Json j) => FitPiece(
        slot: _str(j['slot']),
        source: _str(j['source'], 'catalog'),
        closetItem: j['closet_item'] is Map ? ClosetItem.fromJson(_obj(j['closet_item'])) : null,
        product: j['product'] is Map ? Product.fromJson(_obj(j['product'])) : null,
        yourSize: _strN(j['your_size']),
        inYourSize: _boolN(j['in_your_size']),
      );
}

/// A complete outfit from POST /fits/create: built for the user's body scan, mixing closet pieces with new
/// pieces in their size. [tryOnUrl] is null until the app asks for it (`Api.fitTryOn`).
class OutfitFit {
  const OutfitFit({
    required this.id,
    required this.name,
    required this.reason,
    required this.pieces,
    required this.newTotalUsd,
    required this.closetCount,
    this.occasion,
    this.tryOnUrl,
    this.tryOnMode,
    this.tryOnSourcePhotoUrl,
  });
  final String id;
  final String name;
  final String? occasion;
  final String reason;
  final List<FitPiece> pieces;
  final double newTotalUsd;
  final int closetCount;
  final String? tryOnUrl;
  final String? tryOnMode; // "ai" | "collage"
  final String? tryOnSourcePhotoUrl; // the user's photo the try-on was edited from (see TryOnResponse.sourcePhotoUrl)

  List<FitPiece> get newPieces => pieces.where((p) => !p.fromCloset).toList();

  factory OutfitFit.fromJson(Json j) {
    final t = j['try_on'] is Map ? _obj(j['try_on']) : null;
    return OutfitFit(
      id: _str(j['id']),
      name: _str(j['name']),
      occasion: _strN(j['occasion']),
      reason: _str(j['reason']),
      pieces: _list(j['pieces'], FitPiece.fromJson),
      newTotalUsd: _dbl(j['new_total_usd']),
      closetCount: _int(j['closet_count']),
      tryOnUrl: t == null ? null : _strN(t['image_url']),
      tryOnMode: t == null ? null : _strN(t['mode']),
      tryOnSourcePhotoUrl: t == null ? null : _strN(t['source_photo_url']),
    );
  }
}
