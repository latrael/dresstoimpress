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

  /// Absolute URL for an image the server returns ("/static/..." paths get the base URL).
  String imageUrl(String url) => url.startsWith('/') ? '${settings.base}$url' : url;

  // ------------------------------------------------------------ health / browse

  Future<bool> health() async => (await _send('GET', '/health', auth: false))['ok'] == true;

  Future<List<FeedCard>> feed({int limit = 20, String? category, String? retailer}) async => _listOf(
      await _send('GET', '/feed',
          query: {'user_id': _user, 'limit': '$limit', 'category': category, 'retailer': retailer}),
      RankedProduct.fromJson);

  Future<Product> product(String id) async => Product.fromJson(await _send('GET', '/products/${_seg(id)}'));

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

  Future<CheckoutResult> checkout() async => CheckoutResult.fromJson(await _send('POST', '/checkout/${_seg(_user)}'));

  Future<List<Order>> orders() async => _listOf(await _send('GET', '/orders/${_seg(_user)}'), Order.fromJson);

  // ------------------------------------------------------------ AI (Adam)

  Future<SizeAdvice> sizeAdvice(String productId,
          {double? heightCm, double? weightKg, String fit = 'regular', double? shoeUs, double? waistIn}) async =>
      SizeAdvice.fromJson(await _send('POST', '/size', body: {
        'product_id': productId,
        'height_cm': heightCm ?? settings.heightCm,
        'weight_kg': weightKg ?? settings.weightKg,
        'fit': fit,
        'shoe_us': shoeUs,
        'waist_in': waistIn,
      }));

  Future<TryOnResponse> tryOn(List<String> productIds, {List<String> closetItemIds = const []}) async =>
      TryOnResponse.fromJson(await _send('POST', '/tryon',
          body: {'user_id': _user, 'product_ids': productIds, 'closet_item_ids': closetItemIds}));

  Future<CompleteLook> completeLook(String productId, {double? budgetUsd}) async => CompleteLook.fromJson(
      await _send('POST', '/complete-look', body: {'user_id': _user, 'product_id': productId, 'budget_usd': budgetUsd}));

  Future<FitScore> fitScore(
          {List<FitTag> items = const [], List<String> productIds = const [], List<String> closetItemIds = const []}) async =>
      FitScore.fromJson(await _send('POST', '/ai/fit-score', body: {
        'items': items.map((t) => t.toJson()).toList(),
        'product_ids': productIds,
        'closet_item_ids': closetItemIds,
      }));

  Future<List<FitTag>> tagFit(String imageUrl) async =>
      _listOf(await _send('POST', '/ai/tag-fit', body: {'image_url': imageUrl}), FitTag.fromJson);

  Future<List<RankedProduct>> shopFit({List<FitTag> tagged = const [], String? photoUrl}) async => _listOf(
      await _send('POST', '/ai/shop-fit',
          body: {'viewer_id': _user, 'tagged': tagged.map((t) => t.toJson()).toList(), 'photo_url': photoUrl}),
      RankedProduct.fromJson);

  Future<StyleProfile> style() async => StyleProfile.fromJson(await _send('GET', '/users/${_seg(_user)}/style'));

  // ------------------------------------------------------------ closet / body photo

  Future<List<ClosetItem>> closet() async => _listOf(await _send('GET', '/closet/${_seg(_user)}'), ClosetItem.fromJson);

  Future<ClosetItem> uploadClosetItem(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      ClosetItem.fromJson(await _upload('/closet/upload', {'user_id': _user}, bytes, mimeType));

  Future<ClosetDeleteResult> deleteClosetItem(String itemId) async =>
      ClosetDeleteResult.fromJson(await _send('DELETE', '/closet/${_seg(_user)}/${_seg(itemId)}'));

  Future<String> uploadBodyPhoto(List<int> bytes, {String mimeType = 'image/jpeg'}) async =>
      _str((await _upload('/users/${_seg(_user)}/body-photo', {}, bytes, mimeType))['body_photo_url']);

  // ------------------------------------------------------------ Fit Check (Nabil)

  Future<List<FitCheckPost>> fitCheckFeed({int limit = 20}) async => _listOf(
      await _send('GET', '/fitcheck/feed', query: {'user_id': _user, 'limit': '$limit'}), FitCheckPost.fromJson);

  Future<FitCheckPost> fitCheckPost(String postId) async =>
      FitCheckPost.fromJson(await _send('GET', '/fitcheck/${_seg(postId)}', query: {'user_id': _user}));

  Future<FitCheckPost> createFitCheck({required String photoUrl, String? caption, List<FitTag>? tagged}) async =>
      FitCheckPost.fromJson(await _send('POST', '/fitcheck', body: {
        'user_id': _user,
        'photo_url': photoUrl,
        'caption': caption,
        'tagged': tagged?.map((t) => t.toJson()).toList(),
      }));

  Future<FitCheckPost> createFitCheckUpload(List<int> bytes, {String? caption, String mimeType = 'image/jpeg'}) async =>
      FitCheckPost.fromJson(
          await _upload('/fitcheck', {'user_id': _user, if (caption != null) 'caption': caption}, bytes, mimeType));

  Future<FitCheckPost> updateFitCheckTags(String postId, List<FitTag> tagged) async => FitCheckPost.fromJson(await _send(
      'PATCH', '/fitcheck/${_seg(postId)}/tags',
      body: {'user_id': _user, 'tagged': tagged.map((t) => t.toJson()).toList()}));

  Future<List<RankedProduct>> shopFitCheck(String postId) async => _listOf(
      await _send('GET', '/fitcheck/${_seg(postId)}/shop', query: {'user_id': _user}), RankedProduct.fromJson);

  Future<LikeResult> likeFitCheck(String postId) async =>
      LikeResult.fromJson(await _send('POST', '/fitcheck/${_seg(postId)}/like', body: {'user_id': _user}));

  Future<FitCheckComment> commentFitCheck(String postId, String text) async => FitCheckComment.fromJson(
      await _send('POST', '/fitcheck/${_seg(postId)}/comments', body: {'user_id': _user, 'text': text}));

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
    return _perform(req);
  }

  /// multipart/form-data: text [fields] plus one image in field `file`. Built by hand so the image part
  /// carries its real Content-Type (the server rejects anything that isn't jpeg/png/webp/heic).
  Future<dynamic> _upload(String path, Map<String, String> fields, List<int> bytes, String mimeType) async {
    final boundary = 'dti-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(1 << 30)}';
    final ext = mimeType.split('/').last;
    final out = BytesBuilder();
    void add(String s) => out.add(utf8.encode(s));
    for (final f in fields.entries) {
      add('--$boundary\r\nContent-Disposition: form-data; name="${f.key}"\r\n\r\n${f.value}\r\n');
    }
    add('--$boundary\r\nContent-Disposition: form-data; name="file"; filename="photo.$ext"\r\n');
    add('Content-Type: $mimeType\r\n\r\n');
    out.add(bytes);
    add('\r\n--$boundary--\r\n');

    final req = http.Request('POST', _uri(path, null))
      ..headers['X-DTI-Key'] = settings.apiKey
      ..headers['Content-Type'] = 'multipart/form-data; boundary=$boundary'
      ..bodyBytes = out.takeBytes();
    return _perform(req);
  }

  Future<dynamic> _perform(http.Request req) async {
    // first feed load and fresh try-ons take a few seconds
    final streamed = await _client.send(req).timeout(const Duration(seconds: 60));
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
