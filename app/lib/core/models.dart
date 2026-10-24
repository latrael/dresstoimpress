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
  // AI tags (filled at ingest)
  final String? label;
  final List<String> styleTags;
  final String? pattern;
  final int? formality;
  final String? source;

  /// Price to charge: the sale price when it's set and lower.
  double get effectivePrice => (salePriceUsd != null && salePriceUsd! < priceUsd) ? salePriceUsd! : priceUsd;
  bool get isOnSale => effectivePrice < priceUsd;

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
        label: _strN(j['label']),
        styleTags: _strs(j['style_tags']),
        pattern: _strN(j['pattern']),
        formality: _intN(j['formality']),
        source: _strN(j['source']),
      );
}

/// A Product plus the AI ranking fields (feed cards, "shop this fit" results), from the same flat JSON.
class RankedProduct {
  const RankedProduct({required this.product, this.reason, this.score, this.pairsWith = const [], this.matchedTag});
  final Product product;
  final String? reason;
  final double? score;
  final List<String> pairsWith;
  final String? matchedTag; // shop-the-fit only

  String get id => product.id;

  factory RankedProduct.fromJson(Json j) => RankedProduct(
        product: Product.fromJson(j),
        reason: _strN(j['reason']),
        score: _dblN(j['score']),
        pairsWith: _strs(j['pairs_with']),
        matchedTag: _strN(j['matched_tag']),
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
  const CartItem({required this.productId, required this.size, required this.qty, this.addedAt, this.product});
  final String productId;
  final String size;
  final int qty;
  final String? addedAt;
  final Product? product;

  factory CartItem.fromJson(Json j) => CartItem(
        productId: _str(j['product_id']),
        size: _str(j['size']),
        qty: _int(j['qty'], 1),
        addedAt: _strN(j['added_at']),
        product: j['product'] is Map ? Product.fromJson(_obj(j['product'])) : null,
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

class Cart {
  const Cart({required this.userId, required this.groups, required this.totalUsd, required this.count});
  final String userId;
  final List<CartGroup> groups;
  final double totalUsd;
  final int count;

  factory Cart.fromJson(Json j) => Cart(
      userId: _str(j['user_id']),
      groups: _list(j['groups'], CartGroup.fromJson),
      totalUsd: _dbl(j['total_usd']),
      count: _int(j['count']));
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
  const TryOnResponse({required this.imageUrl, required this.cached, this.mode});
  final String imageUrl;
  final bool cached;
  final String? mode; // "ai" = real try-on, "collage" = outfit board

  bool get isOutfitBoard => mode == 'collage';

  factory TryOnResponse.fromJson(Json j) =>
      TryOnResponse(imageUrl: _str(j['image_url']), cached: j['cached'] == true, mode: _strN(j['mode']));
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
      {required this.items, required this.newItemsTotalUsd, required this.missing, this.anchorId, this.score});
  final String? anchorId;
  final List<LookItem> items;
  final double newItemsTotalUsd;
  final List<String> missing;
  final double? score;

  factory CompleteLook.fromJson(Json j) => CompleteLook(
        anchorId: _strN(j['anchor_id']),
        items: _list(j['items'], LookItem.fromJson),
        newItemsTotalUsd: _dbl(j['new_items_total_usd']),
        missing: _strs(j['missing']),
        score: _dblN(j['score']),
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

class FitScore {
  const FitScore({required this.score, required this.verdict, required this.notes, required this.breakdown});
  final int score;
  final String verdict;
  final List<String> notes;
  final FitScoreBreakdown breakdown;

  factory FitScore.fromJson(Json j) => FitScore(
      score: _int(j['score']),
      verdict: _str(j['verdict']),
      notes: _strs(j['notes']),
      breakdown: FitScoreBreakdown.fromJson(_obj(j['breakdown'])));
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
      this.bodyPhotoUrl, this.friends = const [], this.bodyProfile});

  final String id;
  final String displayName;
  final String styleText;
  final Map<String, List<double>> priceRanges; // category -> [min, max]
  final String? bodyPhotoUrl;
  final List<String> friends;
  final BodyProfile? bodyProfile; // null until the user does a body scan

  factory AppUser.fromJson(Json j) => AppUser(
        id: _str(j['id']),
        displayName: _str(j['display_name']),
        styleText: _str(j['style_text']),
        priceRanges: _ranges(j['price_ranges']),
        bodyPhotoUrl: _strN(j['body_photo_url']),
        friends: _strs(j['friends']),
        bodyProfile: j['body_profile'] is Map ? BodyProfile.fromJson(_obj(j['body_profile'])) : null,
      );
}

/// Estimated measurements from POST /users/{id}/body-scan (inches). Every number is an estimate and
/// may be null. [source] is "ai" (read from the photo) or "estimate" (height/weight formula).
class BodyProfile {
  const BodyProfile({required this.heightCm, this.weightKg, this.chestIn, this.waistIn, this.hipIn, this.inseamIn,
      this.build, required this.source, this.fullBody, this.note = '', this.scannedAt});

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
      );
}

/// POST /users/{id}/body-scan.
class BodyScanResult {
  const BodyScanResult({required this.bodyPhotoUrl, required this.profile});

  final String bodyPhotoUrl;
  final BodyProfile profile;

  factory BodyScanResult.fromJson(Json j) =>
      BodyScanResult(bodyPhotoUrl: _str(j['body_photo_url']), profile: BodyProfile.fromJson(_obj(j['body_profile'])));
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
  });

  final String id;
  final String userId;
  final String imageUrl;
  final String category;
  final String color;
  final String? pattern;
  final List<String> styleTags;
  final int? formality;
  final String? source;
  final String? label;
  final String? duplicateOf; // set on upload when it looks like something already in the closet

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
      );

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
      };
}

class FitCheckComment {
  const FitCheckComment({required this.id, required this.userId, required this.text, this.createdAt, this.commentCount});
  final String id;
  final String userId;
  final String text;
  final String? createdAt;
  final int? commentCount; // only on the POST .../comments response

  factory FitCheckComment.fromJson(Json j) => FitCheckComment(
      id: _str(j['id']),
      userId: _str(j['user_id']),
      text: _str(j['text']),
      createdAt: _strN(j['created_at']),
      commentCount: _intN(j['comment_count']));
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
  });

  final String id;
  final String userId;
  final String photoUrl;
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
    );
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
