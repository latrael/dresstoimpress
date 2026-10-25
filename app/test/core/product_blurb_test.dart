import 'package:flutter_test/flutter_test.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/features/store/store_controller.dart';

Product _p(String? description, {String? summary}) => Product.fromJson({
      'id': 'hm:1',
      'retailer': 'hm',
      'name': 'Tee',
      'category': 'top',
      'price_usd': 10,
      'image_url': '',
      'description': description,
      'summary': summary,
    });

void main() {
  test('blurb prefers the server summary, whole and trimmed', () {
    expect(
        _p('- Ribbed binding at the collar. Soft cotton jersey.',
                summary: '  A soft cotton tee with a ribbed collar.\nKeeps its shape wash after wash. ')
            .blurb(),
        'A soft cotton tee with a ribbed collar. Keeps its shape wash after wash.');
    expect(_p(null, summary: 'A light-wash baggy jean with a relaxed, streetwear fit.').blurb(),
        'A light-wash baggy jean with a relaxed, streetwear fit.');
    expect(_p('First sentence. Second.', summary: '  ').blurb(), 'First sentence.'); // blank summary: fallback
  });

  test('blurb caps a long summary the same way', () {
    final long = 'This oversized hoodie is made from a heavy brushed cotton blend with a double layer hood and a kangaroo pocket for a warm relaxed layered look all winter long';
    final b = _p(null, summary: long).blurb()!;
    expect(b.length <= 111, isTrue);
    expect(b.endsWith('…'), isTrue);
    expect(b.contains(' long'), isFalse);
    expect(_p(null, summary: 'Short.').summary, 'Short.');
  });

  test('blurb is the first sentence, markers stripped', () {
    expect(
        _p('- Ribbed binding at the collar helps the neckline keep its shape. Soft cotton jersey. Regular fit.')
            .blurb(),
        'Ribbed binding at the collar helps the neckline keep its shape.');
  });

  test('blurb caps long sentences at a word boundary', () {
    final long = 'This oversized hoodie is made from a heavy brushed cotton blend with a double layer hood and a kangaroo pocket for a warm relaxed layered look all winter long';
    final b = _p(long).blurb()!;
    expect(b.length <= 111, isTrue);
    expect(b.endsWith('…'), isTrue);
    expect(b.contains(' long'), isFalse);
  });

  test('blurb is null without a description', () {
    expect(_p(null).blurb(), isNull);
    expect(_p('  ').blurb(), isNull);
  });

  test('browseMap sends the blurb, not the full text', () {
    final card = browseMap(RankedProduct(product: _p('Short one. Then a lot more text that nobody reads.')));
    expect(card['description'], 'Short one.');
  });
}
