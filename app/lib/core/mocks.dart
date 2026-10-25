// Sprint 4 mock data (Adam) so the reels Home (§6) can be built before the backend fields land.
// Same JSON shape as GET /feed cards with the §10.1 fields; parsed with the real fromJson.
import 'models.dart';

const _img = 'https://images.unsplash.com/photo-';

const List<Map<String, dynamic>> mockReelsJson = [
  {
    'id': 'mock:jeans', 'retailer': 'hm', 'name': 'Baggy Jeans', 'category': 'bottom', 'price_usd': 39.99,
    'image_url': '${_img}1541099649105-f69ad21f3246?w=900', 'hero_image_url': '${_img}1542272604-787c3835535d?w=900',
    'in_stock': true, 'reason': 'Light wash to balance your black tee', 'score': 0.82, 'your_size': '32',
    'in_your_size': true,
    'closet_picks': [
      {'id': 'ci_tee', 'label': 'black tee', 'category': 'top', 'image_url': '${_img}1521572163474-6864f9cf17ab?w=600'},
      {'id': 'ci_sneak', 'label': 'white sneakers', 'category': 'shoes', 'image_url': '${_img}1549298916-b41d501d3772?w=600'},
      {'id': 'ci_jkt', 'label': 'denim jacket', 'category': 'outerwear', 'image_url': '${_img}1576871337632-b9aef4c17ab9?w=600'},
      {'id': 'ci_chain', 'label': 'silver chain', 'category': 'accessory', 'image_url': '${_img}1611652022419-a9419f74343d?w=600'},
    ],
    'tryon': {'status': 'ready', 'image_url': '${_img}1515886657613-9f3515b0c78f?w=900', 'mode': 'ai'},
  },
  {
    'id': 'mock:dress', 'retailer': 'zara', 'name': 'Satin Slip Dress', 'category': 'dress', 'price_usd': 49.9,
    'image_url': '${_img}1595777457583-95e059d581b8?w=900', 'in_stock': true,
    'reason': 'Clean lines that match your minimalist pieces', 'score': 0.74,
    'closet_picks': [
      {'id': 'ci_heels', 'label': 'black heels', 'category': 'shoes', 'image_url': '${_img}1543163521-1bf539c55dd2?w=600'},
      {'id': 'ci_bag', 'label': 'shoulder bag', 'category': 'accessory', 'image_url': '${_img}1584917865442-de89df76afd3?w=600'},
    ],
    'tryon': {'status': 'pending'},
  },
  {
    'id': 'mock:tee', 'retailer': 'uniqlo', 'name': 'Supima Cotton Tee', 'category': 'top', 'price_usd': 14.9,
    'image_url': '${_img}1521572163474-6864f9cf17ab?w=900', 'in_stock': true, 'reason': 'An easy base layer',
    'closet_picks': <Map<String, dynamic>>[],
    'tryon': {'status': 'needs_photo'},
  },
  {
    'id': 'mock:coat', 'retailer': 'abercrombie', 'name': 'Wool-Blend Coat', 'category': 'outerwear',
    'price_usd': 180.0, 'image_url': '${_img}1539533018447-63fcce2678e3?w=900', 'in_stock': true,
    'reason': 'Warm layer over your knitwear',
    'tryon': {'status': 'unavailable'},
  },
];

/// Four feed cards covering every slide-2 state (ready, pending, needs_photo, unavailable) and 0-4 closet picks.
List<FeedCard> mockReelsFeed() => mockReelsJson.map(RankedProduct.fromJson).toList();
