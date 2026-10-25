import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'models.dart';
import 'settings.dart';

/// Server error. [message] is the `detail` text; [unavailable] is set on checkout 409
/// (something sold out after it went in the cart: nothing was charged).
class ApiError implements Exception {
  ApiError(this.status, this.message, [this.unavailable = const []]);
  final int status;
  final String message;
  final List<({String productId, String? size})> unavailable;

  @override
  String toString() => message;
}

/// One async method per backend route. Every call sends `X-DTI-Key` except /health and /static.
/// Pure Dart (no Flutter imports).
class Api {
  Api({http.Client? client}) : _client = client ?? http.Client();

  static final Api instance = Api();

  final http.Client _client;
  Settings settings = const Settings();

  String get _user => settings.userId;

  /// Absolute URL for an image the server returns ("/static/..." paths get the base URL). Our own photos
  /// (uploads, try-ons) saved under an older server address are loaded from the current one.
  String imageUrl(String url) => url.startsWith('/') ? '${settings.base}$url' : _ownImage(url);

  // Uploads and try-ons are stored with the server address current when they were saved. The tunnel
  // URL changes (and the backup server has its own), so always load them from the connected server.
  static final _ownStatic = RegExp(r'^https?://[^/?#]+(/static/(?:uploads|tryon)/[^?#]+)$');

  String _ownImage(String url) {
    final m = _ownStatic.firstMatch(url);
    return m == null || settings.base.isEmpty ? url : '${settings.base}${m.group(1)}';
  }

  /// Retailer image hosts the backend's `GET /img?url=` will re-serve (same list as backend/app/main.py).
  static const imageProxyHosts = {
    'image.hm.com', 'lp2.hm.com', 'image.uniqlo.com', 'picsum.photos', 'fastly.picsum.photos', 'images.unsplash.com',
    'cdn.shopify.com', // Princess Polly, True Classic, Brandy Melville, Edikted, Kith, Stüssy (PR #44)
  };

  /// Image URL that loads in a web build: "/static/..." gets the base URL; retailer images go through
  /// `GET /img?url=` (no key; retailer servers refuse direct loads from a web app); anything else as-is.
  String imageProxyUrl(String url) {
    if (url.startsWith('/')) return '${settings.base}$url';
    final own = _ownImage(url);
    if (own != url) return own;
    final u = Uri.tryParse(url);
    if (u == null || u.scheme != 'https' || !imageProxyHosts.contains(u.host)) return url;
    return Uri.parse('${settings.base}/img').replace(queryParameters: {'url': url}).toString();
  }

  // ------------------------------------------------------------ sign-in (docs/auth-google.md)

  /// POST /auth/google: a Google ID token -> our session token + the user. `created` = a new user (onboard
  /// them). [linkUserId] attaches this Google account once to an existing user (a team account).
  Future<GoogleSession> signInWithGoogle(String idToken, {String? linkUserId}) async => GoogleSession.fromJson(
      await _send('POST', '/auth/google', body: {'id_token': idToken, 'link_user_id': linkUserId}));

  /// GET /auth/me: the signed-in user, or ApiError 401 if the saved token is missing, expired or revoked.
  Future<AppUser> me() async => AppUser.fromJson(await _send('GET', '/auth/me'));

  /// POST /auth/logout: the session token stops working on the server.
  Future<void> logout() async => _send('POST', '/auth/logout');

  // ------------------------------------------------------------ health / browse

  Future<bool> health() async => (await _send('GET', '/health', auth: false))['ok'] == true;

  /// GET /feed. Cards carry [RankedProduct.yourSize] / [inYourSize] (soft size ranking, D3). With [seed]
  /// (a product id) the feed is "seeded" (D9): that item first, then similar items in your size.
  /// [seedShown] (only meaningful with [seed]): the app has already shown the seed card, so this reload of
  /// the same seeded feed leaves it out. Sends `seed_shown=true` only when true.
  Future<List<FeedCard>> feed(
          {int limit = 20, String? category, String? retailer, String? seed, bool seedShown = false}) async =>
      _listOf(
          await _send('GET', '/feed', query: {
            'user_id': _user, 'limit': '$limit', 'category': category, 'retailer': retailer, 'seed': seed,
            'seed_shown': seedShown ? 'true' : null,
          }),
          RankedProduct.fromJson);

  /// POST /feed/{user}/tryons {product_ids} (sprint 4 §10.2): start rendering slide-2 try-ons in the
  /// background for up to 5 posts (call on feed load for posts 1-3, then n+1..n+3 as the user lands on n).
  /// Returns immediately with each product's [TryOnState] (usually pending).
  Future<Map<String, TryOnState>> prefetchTryOns(List<String> productIds) async => _tryOnMap(await _send(
      'POST', '/feed/${_seg(_user)}/tryons', body: {'product_ids': productIds.take(5).toList()}));

  /// GET /feed/{user}/tryons?ids=a,b,c: current slide-2 states, for polling (~3 s while a visible post is
  /// pending; stop once ready).
  Future<Map<String, TryOnState>> tryOnStatus(List<String> productIds) async => _tryOnMap(
      await _send('GET', '/feed/${_seg(_user)}/tryons', query: {'ids': productIds.join(',')}));

  static Map<String, TryOnState> _tryOnMap(dynamic j) => j is Map
      ? {for (final e in j.entries) if (e.value is Map) '${e.key}': TryOnState.fromJson(Map<String, dynamic>.from(e.value as Map))}
      : <String, TryOnState>{};

  // ------------------------------------------------------------ Discover (Nabil's routes, Adam's vibe parser)

  /// GET /search?user_id=&q=: keyword search (a style, an item) -> "Similar items" (Products, in stock, one
  /// per style) + "Goes with it" around the top result (D10). Blank [q] -> empty lists.
  Future<SearchResult> search(String q) async =>
      SearchResult.fromJson(await _send('GET', '/search', query: {'user_id': _user, 'q': q}));

  /// GET /search/styles?user_id=&limit=: the catalog's style tags with counts (chips, most common first)
  /// and up to [limit] trending products (D11).
  Future<StyleChips> searchStyles({int limit = 8}) async =>
      StyleChips.fromJson(await _send('GET', '/search/styles', query: {'user_id': _user, 'limit': '$limit'}));

  /// POST /search/photo (multipart `user_id` + `file`): the AI tags each piece in the photo, finds catalog
  /// matches and what completes the top one. Creates no post or closet item; GPS is stripped. 502
  /// (ApiError) when the AI is down, 415/413 for a bad file; no garments -> 200 with empty lists.
  Future<PhotoSearchResult> searchPhoto(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      PhotoSearchResult.fromJson(await _upload('/search/photo', {'user_id': _user}, bytes, mimeType));

  /// GET /stores: the retailers we carry, biggest first (`StoreInfo{id, name, count, departments}`), for
  /// onboarding chips and cart headings. Also fills the pure name cache behind [StoreInfo.nameFor], so
  /// `retailerName(id)` can show server names after one call per app start (fallback: the id).
  Future<List<StoreInfo>> stores() async {
    final list = _listOf(await _send('GET', '/stores'), StoreInfo.fromJson);
    StoreInfo.remember(list);
    return list;
  }

  Future<Product> product(String id) async => Product.fromJson(await _send('GET', '/products/${_seg(id)}'));

  /// GET /products: catalog search + paging (Nabil). Every word of [q] must match; `nextOffset` is null
  /// on the last page. [sort]: relevance | price_asc | price_desc.
  Future<ProductPage> searchProducts({String q = '', String? category, String? retailer, bool inStock = true,
          String sort = 'relevance', int limit = 24, int offset = 0}) async =>
      ProductPage.fromJson(await _send('GET', '/products', query: {
        'q': q, 'category': category, 'retailer': retailer, 'in_stock': '$inStock', 'sort': sort,
        'limit': '$limit', 'offset': '$offset',
      }));

  // ------------------------------------------------------------ wishlist (hearts; never dismisses from the feed)

  Future<List<String>> wishlistIds() async =>
      ((await _send('GET', '/wishlist/${_seg(_user)}/ids')) as List).map((e) => '$e').toList();

  Future<List<Product>> wishlist() async => _listOf(await _send('GET', '/wishlist/${_seg(_user)}'), Product.fromJson);

  Future<WishlistResult> save(String productId) async =>
      WishlistResult.fromJson(await _send('PUT', '/wishlist/${_seg(_user)}/items/${_seg(productId)}'));

  Future<WishlistResult> unsave(String productId) async =>
      WishlistResult.fromJson(await _send('DELETE', '/wishlist/${_seg(_user)}/items/${_seg(productId)}'));

  /// Deliberate keep/skip buttons only. Never call for photo swipes or vertical browsing:
  /// any /swipe removes the product from the feed.
  Future<SwipeResult> swipe(String productId, String action, {String? size}) async => SwipeResult.fromJson(
      await _send('POST', '/swipe', body: {'user_id': _user, 'product_id': productId, 'action': action, 'size': size}));

  // ------------------------------------------------------------ cart / checkout (Nabil)

  Future<Cart> cart() async => Cart.fromJson(await _send('GET', '/cart/${_seg(_user)}'));

  Future<Cart> addToCart(String productId, String size, {int qty = 1}) async => Cart.fromJson(await _send(
      'POST', '/cart/${_seg(_user)}/items', body: {'product_id': productId, 'size': size, 'qty': qty}));

  Future<Cart> removeFromCart(String productId, {String? size}) async => Cart.fromJson(
      await _send('DELETE', '/cart/${_seg(_user)}/items/${_seg(productId)}', query: {'size': size}));

  /// PATCH /cart/{user}/items/{product_id}: atomic size change (the cart pencil). Keeps the quantity and
  /// merges into an existing line of [newSize]. Replaces the old add-then-remove pair that could half-fail.
  Future<Cart> changeCartSize(String productId, {required String size, required String newSize}) async =>
      Cart.fromJson(await _send('PATCH', '/cart/${_seg(_user)}/items/${_seg(productId)}',
          body: {'size': size, 'new_size': newSize}));

  Future<CheckoutResult> checkout() async => CheckoutResult.fromJson(await _send('POST', '/checkout/${_seg(_user)}'));

  Future<List<Order>> orders() async => _listOf(await _send('GET', '/orders/${_seg(_user)}'), Order.fromJson);

  /// POST /orders/{id}/retry: re-attempts only this order's unpaid store purchases (`nessie_failed` /
  /// `pending_nessie`), or just [retailer]'s. Paid purchases are never charged again, so it is safe to
  /// repeat. Returns the updated receipt. ApiError 503 when payments aren't configured on the server.
  Future<CheckoutResult> retryOrder(String orderId, {String? retailer}) async => CheckoutResult.fromJson(
      await _send('POST', '/orders/${_seg(orderId)}/retry',
          query: {'user_id': _user, if (retailer != null) 'retailer': retailer}));

  // ------------------------------------------------------------ AI (Adam)

  Future<SizeAdvice> sizeAdvice(String productId,
          {double? heightCm, double? weightKg, String fit = 'regular', double? shoeUs, double? waistIn, bool useSavedProfile = false}) async =>
      SizeAdvice.fromJson(await _send('POST', '/size', body: {
        'product_id': productId,
        'user_id': _user, // the backend fills a missing waist (and height/weight) from the user's body scan
        'height_cm': useSavedProfile ? heightCm : heightCm ?? settings.heightCm,
        'weight_kg': useSavedProfile ? weightKg : weightKg ?? settings.weightKg,
        'fit': fit,
        'shoe_us': shoeUs,
        'waist_in': waistIn,
      }));

  Future<TryOnResponse> tryOn(List<String> productIds, {List<String> closetItemIds = const []}) async =>
      TryOnResponse.fromJson(await _send('POST', '/tryon',
          body: {'user_id': _user, 'product_ids': productIds, 'closet_item_ids': closetItemIds}));

  Future<CompleteLook> completeLook(String productId, {double? budgetUsd}) async => CompleteLook.fromJson(
      await _send('POST', '/complete-look', body: {'user_id': _user, 'product_id': productId, 'budget_usd': budgetUsd}));

  /// POST /fits/create: complete outfits for the user's body scan, mixing closet pieces with new ones in their
  /// size. [tryOn] renders each fit on the body photo (slow); default false, use [fitTryOn] to lazy-load it.
  Future<List<OutfitFit>> createFits(
          {int count = 3, String? occasion, List<String>? mustInclude, double? budgetUsd, bool tryOn = false}) async =>
      _listOf(
          (await _send('POST', '/fits/create', query: {'tryon': tryOn ? 'true' : null}, body: {
            'user_id': _user,
            'count': count,
            'occasion': occasion,
            'must_include': mustInclude,
            'budget_usd': budgetUsd,
          }))['fits'],
          OutfitFit.fromJson);

  /// GET /fits/{id}: a fit from the last hour (ApiError 404 once it expires).
  Future<OutfitFit> fit(String fitId) async =>
      OutfitFit.fromJson(await _send('GET', '/fits/${_seg(fitId)}', query: {'user_id': _user}));

  /// POST /fits/{id}/try-on: the fit on the user's body photo ({imageUrl, mode}; `cached` is always false here).
  Future<TryOnResponse> fitTryOn(String fitId) async =>
      TryOnResponse.fromJson(await _send('POST', '/fits/${_seg(fitId)}/try-on', query: {'user_id': _user}));

  /// POST /fits/{id}/cart: every new piece of the fit into the cart at the user's size. Returns the cart.
  Future<Cart> addFitToCart(String fitId) async =>
      Cart.fromJson(await _send('POST', '/fits/${_seg(fitId)}/cart', query: {'user_id': _user}));

  /// POST /ai/fit-score (v2). `targetStyle` scores the outfit as that style (streetwear, minimalist, classic,
  /// y2k, preppy, athleisure, vintage, business, boho, grunge) instead of its best one; `photoUrl` (a Fit Check
  /// post's photo) adds the AI photo critic when the server has AI on; `occasion` adds the occasion criterion.
  Future<FitScore> fitScore(
          {List<FitTag> items = const [],
          List<String> productIds = const [],
          List<String> closetItemIds = const [],
          String? targetStyle,
          String? photoUrl,
          String? occasion}) async =>
      FitScore.fromJson(await _send('POST', '/ai/fit-score', body: {
        'items': items.map((t) => t.toJson()).toList(),
        'product_ids': productIds,
        'closet_item_ids': closetItemIds,
        if (targetStyle != null) 'target_style': targetStyle,
        if (photoUrl != null) 'photo_url': photoUrl,
        if (occasion != null) 'occasion': occasion,
      }));

  Future<List<FitTag>> tagFit(String imageUrl) async =>
      _listOf(await _send('POST', '/ai/tag-fit', body: {'image_url': imageUrl}), FitTag.fromJson);

  Future<List<RankedProduct>> shopFit({List<FitTag> tagged = const [], String? photoUrl}) async => _listOf(
      await _send('POST', '/ai/shop-fit',
          body: {'viewer_id': _user, 'tagged': tagged.map((t) => t.toJson()).toList(), 'photo_url': photoUrl}),
      RankedProduct.fromJson);

  Future<StyleProfile> style() async => StyleProfile.fromJson(await _send('GET', '/users/${_seg(_user)}/style'));

  /// POST /users/{id}/style/apply: saves the learned price ranges on the user (the feed ranks in-budget
  /// items first) and the headline as style_text if empty. 409 (ApiError) with fewer than 5 liked items.
  Future<StyleApplyResult> applyStyle() async =>
      StyleApplyResult.fromJson(await _send('POST', '/users/${_seg(_user)}/style/apply'));

  // ------------------------------------------------------------ users / onboarding (Nabil)

  /// POST /users. 409 if [id] exists. Without [priceRanges], budgets are parsed from [styleText].
  /// [shopFor]: `men` | `women` | `both` (the server defaults to `both` when not sent).
  Future<AppUser> createUser({required String displayName, String? id, String styleText = '',
          Map<String, List<double>>? priceRanges, List<String> friends = const [], String? shopFor}) async =>
      AppUser.fromJson(await _send('POST', '/users', body: {
        'id': id, 'display_name': displayName, 'style_text': styleText, 'price_ranges': priceRanges,
        'friends': friends, 'shop_for': shopFor,
      }));

  /// GET /users/{id} (defaults to the current user). 404 if unknown.
  Future<AppUser> getUser([String? userId]) async =>
      AppUser.fromJson(await _send('GET', '/users/${_seg(userId ?? _user)}'));

  /// PATCH /users/{id} (current user). Only the fields you pass change; new [styleText] without
  /// [priceRanges] re-parses budgets and merges them over the old ones. [preferredStores] are retailer
  /// ids ("hm", "uniqlo"); [onboarded] marks the end of onboarding (D5/D6). [shopFor]: `men` | `women` |
  /// `both` (the feed and Discover filter by it); sent only when non-null.
  Future<AppUser> updateUser({String? displayName, String? styleText, Map<String, List<double>>? priceRanges,
          List<String>? friends, List<String>? preferredStores, bool? onboarded, String? shopFor}) async =>
      AppUser.fromJson(await _send('PATCH', '/users/${_seg(_user)}', body: {
        'display_name': displayName, 'style_text': styleText, 'price_ranges': priceRanges, 'friends': friends,
        'preferred_stores': preferredStores, 'onboarded': onboarded, 'shop_for': shopFor,
      }));

  /// POST /onboarding: create or update a user from free text ("Y2K, tops under $40") and return what
  /// was understood. [userId] defaults to the current user; pass null-able [displayName] for new users.
  Future<OnboardingResult> onboarding(String text, {String? displayName, String? userId}) async =>
      OnboardingResult.fromJson(await _send('POST', '/onboarding',
          body: {'user_id': userId ?? _user, 'display_name': displayName, 'text': text}));

  // ------------------------------------------------------------ closet / body photo

  Future<List<ClosetItem>> closet() async => _listOf(await _send('GET', '/closet/${_seg(_user)}'), ClosetItem.fromJson);

  /// Legacy single-photo call. The backend digitizes it like an outfit (every garment lands in the closet)
  /// but answers with the FIRST piece only. New code uses [uploadClosetPhotos] with `kind: 'outfit'`.
  Future<ClosetItem> uploadClosetItem(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      ClosetItem.fromJson(await _upload('/closet/upload', {'user_id': _user}, bytes, mimeType));

  Future<ClosetDeleteResult> deleteClosetItem(String itemId) async =>
      ClosetDeleteResult.fromJson(await _send('DELETE', '/closet/${_seg(_user)}/${_seg(itemId)}'));

  /// GET /closet/{user}/outfits (sprint-3 §1.3): the user's outfits, newest first, each with its
  /// [ClosetOutfit.pieces] embedded. An outfit is made by every `kind: 'outfit'` upload photo and by every
  /// Fit Check post. The Pieces view is still [closet].
  Future<List<ClosetOutfit>> closetOutfits() async =>
      _listOf(await _send('GET', '/closet/${_seg(_user)}/outfits'), ClosetOutfit.fromJson);

  /// PATCH /closet/{user}/outfits/{id} {name}: the outfit's nickname; blank restores the automatic one.
  Future<ClosetOutfit> renameClosetOutfit(String outfitId, String name) async =>
      ClosetOutfit.fromJson(await _send('PATCH', '/closet/${_seg(_user)}/outfits/${_seg(outfitId)}', body: {'name': name}));

  /// DELETE /closet/{user}/outfits/{id}: removes the outfit only; its pieces stay in the closet.
  Future<ClosetDeleteResult> deleteClosetOutfit(String outfitId) async =>
      ClosetDeleteResult.fromJson(await _send('DELETE', '/closet/${_seg(_user)}/outfits/${_seg(outfitId)}'));

  Future<String> uploadBodyPhoto(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      _str((await _upload('/users/${_seg(_user)}/body-photo', {}, bytes, mimeType))['body_photo_url']);

  /// DELETE /users/{id}/body-photo: forgets the private try-on / body-scan photo and deletes the file.
  /// Measurements from a body scan stay. False when there was no photo (safe to repeat).
  Future<bool> deleteBodyPhoto() async =>
      (await _send('DELETE', '/users/${_seg(_user)}/body-photo'))['deleted'] == true;

  /// Closet v2 upload: 1-8 photos in one call, with intent. `kind` = `'piece'` (each photo is one
  /// garment: tagged directly) or `'outfit'` (each photo is a whole fit: every visible garment is detected
  /// and cropped to its own picture). Pieces that match something already in the closet are not
  /// duplicated: the photo is added to that item's [ClosetItem.wornIn] and it comes back under
  /// [ClosetUploadResult.merged]. [mimeTypes] pairs with [photos] (jpeg when omitted).
  Future<ClosetUploadResult> uploadClosetPhotos(List<List<int>> photos,
      {required String kind, List<String>? mimeTypes}) async {
    assert(kind == 'piece' || kind == 'outfit', 'kind must be piece or outfit');
    final types = [for (var i = 0; i < photos.length; i++) mimeTypes?[i] ?? 'image/jpeg'];
    return ClosetUploadResult.fromJson(await _uploadMany('/closet/upload', {'user_id': _user, 'kind': kind}, photos, types));
  }

  /// One outfit photo -> every garment in it, as closet v2 items (added + merged). Kept for callers of the
  /// old digitize flow; same as `uploadClosetPhotos([bytes], kind: 'outfit').all`.
  Future<List<ClosetItem>> digitizeCloset(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      (await uploadClosetPhotos([bytes], kind: 'outfit', mimeTypes: [mimeType])).all;

  /// PATCH /closet/{user}/{item}: edit one piece. Only the named fields are sent. [clearProduct] sends
  /// `product_id: null` (drops the catalog match; the picture goes back to the clean shot / crop);
  /// [productId] links it to a catalog product (the picture becomes the catalog photo).
  Future<ClosetItem> updateClosetItem(String itemId,
      {String? label, String? brand, String? category, String? color, String? productId, bool clearProduct = false}) async {
    final body = <String, dynamic>{
      if (label != null) 'label': label,
      if (brand != null) 'brand': brand,
      if (category != null) 'category': category,
      if (color != null) 'color': color,
      if (productId != null) 'product_id': productId,
    };
    final req = http.Request('PATCH', _uri('/closet/${_seg(_user)}/${_seg(itemId)}', null))
      ..headers['X-DTI-Key'] = settings.apiKey
      ..headers['Content-Type'] = 'application/json'
      ..body = jsonEncode(clearProduct ? {...body, 'product_id': null} : body);
    return ClosetItem.fromJson(await _perform(req));
  }

  /// POST /closet/{user}/{item}/reshoot: regenerate the piece's clean product shot (slow: image AI).
  Future<ClosetItem> reshootClosetItem(String itemId) async {
    final req = http.Request('POST', _uri('/closet/${_seg(_user)}/${_seg(itemId)}/reshoot', null))
      ..headers['X-DTI-Key'] = settings.apiKey;
    return ClosetItem.fromJson(await _perform(req, timeout: uploadTimeout));
  }

  /// PATCH /users/{id}/body-profile: measurements the user typed (onboarding / profile), saved on the
  /// server so they follow the user to any device; [AppUser.bodyProfile] returns them. Only the fields
  /// passed change. Lengths in cm (the profile stores inches). Typed values win over a body scan.
  /// [usualSizes] maps a category ("top", "bottom", "shoes", ...) to the user's usual size; /size falls
  /// back to it. 422 (ApiError) for impossible values.
  Future<BodyProfile> updateBodyProfile({double? heightCm, double? weightKg, double? waistCm, double? chestCm,
          double? hipCm, double? inseamCm, double? shoeUs, String? fit, Map<String, String>? usualSizes}) async =>
      BodyProfile.fromJson(await _send('PATCH', '/users/${_seg(_user)}/body-profile', body: {
        'height_cm': heightCm, 'weight_kg': weightKg, 'waist_cm': waistCm, 'chest_cm': chestCm, 'hip_cm': hipCm,
        'inseam_cm': inseamCm, 'shoe_us': shoeUs, 'fit': fit, 'usual_sizes': usualSizes,
      }));

  /// POST /users/{id}/body-scan: full-body photo + height (weight optional) -> estimated measurements,
  /// saved on the user and used by [sizeAdvice]. The photo also becomes the try-on photo.
  /// 422 (ApiError) for a height outside 120-230 cm or weight outside 30-250 kg.
  ///
  /// [commit] false = **draft** for a review screen (`?commit=false`): the scan runs and the photo file is
  /// kept, but nothing is saved on the user (no body photo, no measurements) until [confirmBodyScan].
  /// The result then has [BodyScanResult.committed] false. Default true saves right away, as before.
  Future<BodyScanResult> bodyScan(List<int> bytes,
          {required double heightCm, double? weightKg, String mimeType = 'image/jpeg', bool commit = true}) async =>
      BodyScanResult.fromJson(await _upload('/users/${_seg(_user)}/body-scan',
          {'height_cm': '$heightCm', if (weightKg != null) 'weight_kg': '$weightKg'}, bytes, mimeType,
          query: {'commit': commit ? null : 'false'}));

  /// POST /users/{id}/body-scan with several photos (1-6): every full-body photo is scanned and the estimates
  /// averaged ("more photos = better estimate"); `BodyProfile.scanPhotos` / `confidence` (low 1, medium 2,
  /// high 3+) say how many were used, `BodyScanResult.skipped` how many weren't full-body. The first full-body
  /// photo becomes the try-on photo. [mimeTypes] lines up with [photos] (missing -> image/jpeg). Same [commit]
  /// draft semantics as [bodyScan]. 422 (ApiError) for no photos, more than 6, or a bad height / weight.
  Future<BodyScanResult> bodyScanMany(List<List<int>> photos,
          {required double heightCm, double? weightKg, List<String>? mimeTypes, bool commit = true}) async =>
      BodyScanResult.fromJson(await _uploadMany('/users/${_seg(_user)}/body-scan',
          {'height_cm': '$heightCm', if (weightKg != null) 'weight_kg': '$weightKg'}, photos, mimeTypes ?? const [],
          query: {'commit': commit ? null : 'false'}));

  /// POST /users/{id}/body-scan/confirm: saves a reviewed [draft] from `bodyScan(commit: false)`: the photo
  /// becomes the body / try-on photo and the profile is saved as the user's measurements.
  ///
  /// Pass only what the user **changed** on the review screen, in the profile's own units (cm for height,
  /// kg for weight, inches for chest / waist / hip / inseam, US shoe size). Those fields are saved as typed
  /// (`BodyProfile.manual`, they win over later scans); everything else is taken from the draft as the
  /// scan's estimate, so measurements the user typed earlier keep winning over those. Returns the saved
  /// profile with [BodyScanResult.committed] true. ApiError 422 for an impossible number or a draft photo
  /// that isn't one of this server's uploads.
  Future<BodyScanResult> confirmBodyScan(BodyScanResult draft,
      {double? heightCm, double? weightKg, double? chestIn, double? waistIn, double? hipIn, double? inseamIn,
      String? build, String? fit, double? shoeUs}) async {
    final edits = <String, Object?>{
      'height_cm': heightCm, 'weight_kg': weightKg, 'chest_in': chestIn, 'waist_in': waistIn, 'hip_in': hipIn,
      'inseam_in': inseamIn, 'build': build, 'fit': fit, 'shoe_us': shoeUs,
    }..removeWhere((_, v) => v == null);
    return BodyScanResult.fromJson(await _send('POST', '/users/${_seg(_user)}/body-scan/confirm', body: {
      'body_photo_url': draft.bodyPhotoUrl,
      'profile': {...draft.profile.toJson(), ...edits},
      'edited': edits.keys.toList(),
    }));
  }

  /// POST /onboarding/photos ("photo onboarding"): 1-8 photos (outfits, flat lays, mirror selfies) + height
  /// (weight optional) in one call. Every photo is digitized into closet items (duplicates skipped), the best
  /// full-body photo is body-scanned and becomes the try-on photo, and the style is inferred from the
  /// garments and saved as the user's style_text / style_tags (onboarded = true). [styleHint] is what the
  /// user typed, if anything ("Y2K, tops under $40": budgets are parsed like [onboarding]). [mimeTypes]
  /// lines up with [photos]; missing entries default to image/jpeg. 422 (ApiError) for no photos, more than
  /// 8, or a height outside 120-230 cm; 415 if any file isn't an image; 502 only if tagging failed for all.
  Future<PhotoOnboardingResult> onboardFromPhotos(List<List<int>> photos,
          {required double heightCm, double? weightKg, String? styleHint, List<String>? mimeTypes}) async =>
      PhotoOnboardingResult.fromJson(await _uploadMany('/onboarding/photos', {
        'user_id': _user,
        'height_cm': '$heightCm',
        if (weightKg != null) 'weight_kg': '$weightKg',
        if (styleHint != null && styleHint.trim().isNotEmpty) 'style_hint': styleHint.trim(),
      }, photos, mimeTypes ?? const []));

  /// POST /ai/vibe (Discover): a sentence ("fit for a rooftop party") -> catalog filters: styles and
  /// categories from the catalog vocabularies, colors and item keywords. Never 502s (keyword rules
  /// fallback). ApiError 422 for an empty or >200-character query.
  Future<VibeQuery> vibe(String q) async => VibeQuery.fromJson(await _send('POST', '/ai/vibe', body: {'q': q}));

  // ------------------------------------------------------------ Friends (Adam)

  /// GET /users/{me}/code: my handle + friend code (generated on first read) and friends count.
  Future<FriendIdentity> myCode() async =>
      FriendIdentity.fromJson(await _send('GET', '/users/${_seg(_user)}/code'));

  /// GET /users/{me}/friends.
  Future<List<Friend>> friends() async => _listOf(await _send('GET', '/users/${_seg(_user)}/friends'), Friend.fromJson);

  /// POST /users/{me}/friends {handle_or_code}: mutual add by handle (`@nabil`) or code (`NCH-7K2P`).
  /// ApiError 404 when nobody matches, 422 for yourself.
  Future<List<Friend>> addFriend(String handleOrCode) async => _listOf(
      await _send('POST', '/users/${_seg(_user)}/friends', body: {'handle_or_code': handleOrCode}), Friend.fromJson);

  /// DELETE /users/{me}/friends/{id}: mutual remove.
  Future<List<Friend>> removeFriend(String friendId) async =>
      _listOf(await _send('DELETE', '/users/${_seg(_user)}/friends/${_seg(friendId)}'), Friend.fromJson);

  // ------------------------------------------------------------ Fit Check (Nabil)

  /// GET /fitcheck/feed: one Inspo feed for everyone (D4). [author] (a user id) = only that person's posts.
  /// [scope] 'friends' = friends' + own posts; null = everyone (friends-only posts stay in their circle).
  Future<List<FitCheckPost>> fitCheckFeed({int limit = 20, String? author, String? scope}) async => _listOf(
      await _send('GET', '/fitcheck/feed',
          query: {'user_id': _user, 'limit': '$limit', 'author': author, 'scope': scope}),
      FitCheckPost.fromJson);

  Future<FitCheckPost> fitCheckPost(String postId) async =>
      FitCheckPost.fromJson(await _send('GET', '/fitcheck/${_seg(postId)}', query: {'user_id': _user}));

  /// [visibility] 'public' (Everyone, the default) or 'friends'.
  Future<FitCheckPost> createFitCheck(
          {required String photoUrl, String? caption, List<FitTag>? tagged, String visibility = 'public'}) async =>
      FitCheckPost.fromJson(await _send('POST', '/fitcheck', body: {
        'user_id': _user,
        'photo_url': photoUrl,
        'caption': caption,
        'tagged': tagged?.map((t) => t.toJson()).toList(),
        'visibility': visibility,
      }));

  Future<FitCheckPost> createFitCheckUpload(List<int> bytes,
          {String? caption, String mimeType = 'image/jpeg', String visibility = 'public'}) async =>
      FitCheckPost.fromJson(await _upload(
          '/fitcheck',
          {'user_id': _user, if (caption != null) 'caption': caption, 'visibility': visibility},
          bytes,
          mimeType));

  Future<FitCheckPost> updateFitCheckTags(String postId, List<FitTag> tagged) async => FitCheckPost.fromJson(await _send(
      'PATCH', '/fitcheck/${_seg(postId)}/tags',
      body: {'user_id': _user, 'tagged': tagged.map((t) => t.toJson()).toList()}));

  Future<List<RankedProduct>> shopFitCheck(String postId) async => _listOf(
      await _send('GET', '/fitcheck/${_seg(postId)}/shop', query: {'user_id': _user}), RankedProduct.fromJson);

  /// GET /fitcheck/{id}/shop?grouped=true: shop the look, one [ShopTagGroup] per tagged piece in post order,
  /// each with up to 6 similar items (closest match first, the viewer's shop_for respected). A piece with no
  /// match comes back with an empty `products` list so its chip / pin is still shown.
  Future<List<ShopTagGroup>> shopFitCheckGrouped(String postId) async => _listOf(
      await _send('GET', '/fitcheck/${_seg(postId)}/shop', query: {'user_id': _user, 'grouped': 'true'}),
      ShopTagGroup.fromJson);

  /// PUT /fitcheck/{id}/reaction: **idempotent**. Sets the current user's one reaction to [emoji] (one of
  /// [fitCheckReactions]) or clears it with null.
  Future<ReactionResult> setFitCheckReaction(String postId, String? emoji) async => ReactionResult.fromJson(
      await _send('PUT', '/fitcheck/${_seg(postId)}/reaction', body: {'user_id': _user, 'emoji': emoji}));

  /// GET /fitcheck/{id}/similar: find similar look, one [SimilarLookGroup] per tagged piece in post order:
  /// the viewer's own similar closet pieces, then products to buy.
  Future<List<SimilarLookGroup>> similarLook(String postId) async => _listOf(
      await _send('GET', '/fitcheck/${_seg(postId)}/similar', query: {'user_id': _user}), SimilarLookGroup.fromJson);

  Future<LikeResult> likeFitCheck(String postId) async =>
      LikeResult.fromJson(await _send('POST', '/fitcheck/${_seg(postId)}/like', body: {'user_id': _user}));

  /// PUT /fitcheck/{id}/like: **idempotent** like. Sets the current user's like to [liked]; sending the same
  /// state again changes nothing (safe to retry / coalesce from an optimistic toggle). Returns the resulting
  /// state and count. Prefer this over [likeFitCheck] (POST toggle) for a tap target.
  Future<LikeResult> setFitCheckLike(String postId, {required bool liked}) async => LikeResult.fromJson(
      await _send('PUT', '/fitcheck/${_seg(postId)}/like', body: {'user_id': _user, 'liked': liked}));

  /// GET /fitcheck/{id}/comments: one page of comments, oldest -> newest, each with [FitCheckComment.authorName].
  /// No [before]: the newest [limit]. [before] = a comment id (the page's `nextBefore`): the [limit] comments
  /// just older than it. ApiError 422 for an unknown [before].
  Future<FitCheckCommentsPage> fitCheckComments(String postId, {int limit = 20, String? before}) async =>
      FitCheckCommentsPage.fromJson(await _send('GET', '/fitcheck/${_seg(postId)}/comments',
          query: {'user_id': _user, 'limit': '$limit', 'before': before}));

  /// POST .../comments: the new comment (with `author` -> [FitCheckComment.authorName] and the post's new
  /// [FitCheckComment.commentCount]).
  Future<FitCheckComment> commentFitCheck(String postId, String text) async => FitCheckComment.fromJson(
      await _send('POST', '/fitcheck/${_seg(postId)}/comments', body: {'user_id': _user, 'text': text}));

  /// Deletes the current user's own post. Throws [ApiError] 403 for someone else's post, 404 if it's gone.
  Future<bool> deleteFitCheck(String postId) async =>
      (await _send('DELETE', '/fitcheck/${_seg(postId)}', query: {'user_id': _user}))['deleted'] == true;

  // ------------------------------------------------------------ plumbing

  static String _seg(String s) => Uri.encodeComponent(s);
  static String _str(dynamic v) => v == null ? '' : '$v';

  static List<T> _listOf<T>(dynamic data, T Function(Map<String, dynamic>) f) =>
      data is List ? data.whereType<Map>().map((e) => f(Map<String, dynamic>.from(e))).toList() : <T>[];

  Uri _uri(String path, Map<String, String?>? query) {
    final q = <String, String>{
      for (final e in (query ?? const <String, String?>{}).entries)
        if (e.value != null) e.key: e.value!,
    };
    final uri = Uri.parse('${settings.base}$path');
    return q.isEmpty ? uri : uri.replace(queryParameters: q);
  }

  Future<dynamic> _send(String method, String path,
      {Map<String, String?>? query, Map<String, dynamic>? body, bool auth = true}) async {
    final req = http.Request(method, _uri(path, query));
    if (auth) req.headers['X-DTI-Key'] = settings.apiKey;
    if (body != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(Map.of(body)..removeWhere((_, v) => v == null));
    }
    // Image generation (try-on, fits) takes 15-60 s on the server; give it the upload budget.
    final slow = path == '/tryon' || path.startsWith('/fits');
    return _perform(req, timeout: slow ? uploadTimeout : const Duration(seconds: 60));
  }

  /// multipart/form-data: text [fields] plus one image in field `file`. Built by hand so the image part
  /// carries its real Content-Type (the server rejects anything that isn't jpeg/png/webp/heic).
  Future<dynamic> _upload(String path, Map<String, String> fields, List<int> bytes, String mimeType,
          {Map<String, String?>? query}) =>
      _multipart(path, fields, 'file', [bytes], [mimeType], query: query);

  /// Same as [_upload] with several images, all in the repeated field `files` (FastAPI `list[UploadFile]`).
  /// [mimeTypes] lines up with [photos]; anything missing is image/jpeg.
  Future<dynamic> _uploadMany(String path, Map<String, String> fields, List<List<int>> photos, List<String> mimeTypes,
          {Map<String, String?>? query}) =>
      _multipart(path, fields, 'files', photos,
          [for (var i = 0; i < photos.length; i++) i < mimeTypes.length ? mimeTypes[i] : 'image/jpeg'], query: query);

  Future<dynamic> _multipart(String path, Map<String, String> fields, String fileField, List<List<int>> files,
      List<String> mimeTypes, {Map<String, String?>? query}) async {
    final boundary = 'dti-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(1 << 30)}';
    final out = BytesBuilder();
    void add(String s) => out.add(utf8.encode(s));
    for (final f in fields.entries) {
      add('--$boundary\r\nContent-Disposition: form-data; name="${f.key}"\r\n\r\n${f.value}\r\n');
    }
    for (var i = 0; i < files.length; i++) {
      final mimeType = mimeTypes[i];
      final ext = mimeType.split('/').last;
      final name = files.length == 1 && fileField == 'file' ? 'photo.$ext' : 'photo${i + 1}.$ext';
      add('--$boundary\r\nContent-Disposition: form-data; name="$fileField"; filename="$name"\r\n');
      add('Content-Type: $mimeType\r\n\r\n');
      out.add(files[i]);
      add('\r\n');
    }
    add('--$boundary--\r\n');

    final req = http.Request('POST', _uri(path, query))
      ..headers['X-DTI-Key'] = settings.apiKey
      ..headers['Content-Type'] = 'multipart/form-data; boundary=$boundary'
      ..bodyBytes = out.takeBytes();
    return _perform(req, timeout: uploadTimeout);
  }

  /// Photo uploads go through the tunnel and then the AI (scan, digitize, try-on), so they get longer.
  static const uploadTimeout = Duration(seconds: 180);

  Future<dynamic> _perform(http.Request req, {Duration timeout = const Duration(seconds: 60)}) async {
    // Signed in with Google: every call carries our session token (the server pins it to that user).
    if (settings.sessionToken.isNotEmpty) req.headers['Authorization'] = 'Bearer ${settings.sessionToken}';
    // first feed load and fresh try-ons take a few seconds
    final streamed = await _client.send(req).timeout(timeout);
    final res = await http.Response.fromStream(streamed);
    final text = utf8.decode(res.bodyBytes);
    if (res.statusCode < 200 || res.statusCode >= 300) throw _error(res.statusCode, text);
    return text.isEmpty ? null : jsonDecode(text);
  }

  /// `{"detail": "..."}`, `{"detail": {"message", "unavailable"}}` (checkout 409),
  /// or FastAPI validation errors `{"detail": [{"msg": ...}]}`.
  static ApiError _error(int status, String text) {
    final fallback = status == 401 ? 'Missing or wrong key. Check Settings.' : 'Server error $status';
    dynamic detail;
    try {
      final obj = jsonDecode(text);
      detail = obj is Map ? obj['detail'] : null;
    } catch (_) {
      return ApiError(status, fallback);
    }
    if (detail is String) return ApiError(status, detail);
    if (detail is Map) {
      final unavailable = (detail['unavailable'] is List ? detail['unavailable'] as List : const [])
          .whereType<Map>()
          .map((u) => (productId: '${u['product_id']}', size: u['size'] as String?))
          .toList();
      return ApiError(status, _str(detail['message']).isEmpty ? fallback : _str(detail['message']), unavailable);
    }
    if (detail is List) {
      final msgs = detail.whereType<Map>().map((m) => m['msg']).whereType<String>().toList();
      return ApiError(status, msgs.isEmpty ? fallback : msgs.join('; '));
    }
    return ApiError(status, fallback);
  }
}
