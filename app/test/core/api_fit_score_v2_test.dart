// Core (Adam): Fit Score v2 — Api.fitScore(targetStyle/photoUrl/occasion), FitScore.criteria / styleScores /
// primaryStyle, CompleteLook.fitScore. Old-server replies (v1 fields only) must still parse.
import 'dart:convert';

import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/core/models.dart';
import 'package:dress_to_impress/core/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Api _api(List<http.Request> seen, Object Function(http.Request) reply) {
  final api = Api(client: MockClient((r) async {
    seen.add(r);
    return http.Response(jsonEncode(reply(r)), 200, headers: {'content-type': 'application/json'});
  }));
  api.settings = const Settings(baseUrl: 'https://dti.example/', apiKey: 'k', userId: 'u_demo');
  return api;
}

const _v2 = {
  'score': 68,
  'verdict': '68 as streetwear: strong silhouette, palette too busy',
  'notes': ['Three competing colors pull focus.', 'Your oversized hoodie balances your slim cargos.'],
  'breakdown': {'color': 12, 'pattern': 14, 'formality': 18, 'completeness': 18},
  'criteria': [
    {'name': 'color', 'score_10': 3, 'note': 'Three competing colors pull focus.'},
    {'name': 'silhouette', 'score_10': 9, 'note': 'Your oversized hoodie balances your slim cargos.'},
    {'name': 'pattern', 'score_10': 7, 'note': null},
    {'name': 'formality', 'score_10': 9, 'note': 'Every piece matches the same dress code.'},
    {'name': 'style', 'score_10': 9, 'note': 'Your pieces all lean streetwear.'},
    {'name': 'completeness', 'score_10': 9, 'note': null},
    {'name': 'layering', 'score_10': 5, 'note': null},
    {'name': 'occasion', 'score_10': 9, 'note': 'Dressed right for class.'},
  ],
  'style_scores': {
    'streetwear': 88, 'minimalist': 40, 'classic': 35, 'y2k': 30, 'preppy': 28, 'athleisure': 50,
    'vintage': 33, 'business': 20, 'boho': 25, 'grunge': 61,
  },
  'primary_style': 'streetwear',
  'raw_score': 74,
  'source': 'rules+ai',
};

void main() {
  test('fitScore sends the v2 request fields and parses criteria, style scores and primary style', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _v2);
    final s = await api.fitScore(
        items: const [FitTag(label: 'hoodie', category: 'top', color: 'mustard', styleTags: ['streetwear'])],
        productIds: ['hm:1'],
        targetStyle: 'streetwear',
        photoUrl: 'https://dti.example/static/uploads/p.jpg',
        occasion: 'class');
    final r = seen.single;
    expect(r.method, 'POST');
    expect(r.url.path, '/ai/fit-score');
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    expect(body['product_ids'], ['hm:1']);
    expect(body['closet_item_ids'], isEmpty);
    expect((body['items'] as List).single['label'], 'hoodie');
    expect(body['target_style'], 'streetwear');
    expect(body['photo_url'], 'https://dti.example/static/uploads/p.jpg');
    expect(body['occasion'], 'class');

    expect(s.score, 68);
    expect(s.verdict, startsWith('68 as streetwear:'));
    expect(s.primaryStyle, 'streetwear');
    expect(s.rawScore, 74);
    expect(s.source, 'rules+ai');
    expect(s.breakdown.color, 12);
    expect(s.breakdown.completeness, 18);
    expect(s.criteria, hasLength(8));
    expect(s.criteria.first.name, 'color');
    expect(s.criteria.first.score10, 3);
    expect(s.criteria.first.note, 'Three competing colors pull focus.');
    expect(s.criteria[2].note, isNull);
    expect(s.criteria.map((c) => c.name), contains('occasion'));
    expect(s.styleScores, hasLength(10));
    expect(s.styleScores['streetwear'], 88);
    expect(s.styleScores['business'], 20);
  });

  test('fitScore omits the optional fields when not given (old servers ignore nothing)', () async {
    final seen = <http.Request>[];
    final api = _api(seen, (_) => _v2);
    await api.fitScore(closetItemIds: ['ci1']);
    final body = jsonDecode(seen.single.body) as Map<String, dynamic>;
    expect(body.keys.toSet(), {'items', 'product_ids', 'closet_item_ids'});
    expect(body['closet_item_ids'], ['ci1']);
  });

  test('a v1 reply (no v2 fields) still parses with empty criteria and no primary style', () {
    final s = FitScore.fromJson(const {
      'score': 85,
      'verdict': 'Clean neutrals, one pop',
      'notes': ['a', 'b'],
      'breakdown': {'color': 40, 'pattern': 20, 'formality': 20, 'completeness': 5},
    });
    expect(s.score, 85);
    expect(s.criteria, isEmpty);
    expect(s.styleScores, isEmpty);
    expect(s.primaryStyle, isNull);
    expect(s.rawScore, isNull);
    expect(s.source, isNull);
    expect(s.breakdown.completeness, 5);
  });

  test('FitCriterion tolerates missing note and numeric strings', () {
    final c = FitCriterion.fromJson(const {'name': 'style', 'score_10': 7});
    expect(c.name, 'style');
    expect(c.score10, 7);
    expect(c.note, isNull);
  });

  test('CompleteLook carries the completed outfit Fit Score and primary style', () {
    final look = CompleteLook.fromJson({
      'anchor_id': 'p-ath-tee',
      'items': [
        {'source': 'catalog', 'id': 'p-joggers', 'category': 'bottom', 'label': 'Fleece joggers', 'reason': 'x'},
      ],
      'new_items_total_usd': 65.0,
      'missing': ['shoes'],
      'score': 0.71,
      'fit_score': {..._v2, 'primary_style': 'athleisure', 'verdict': '61 as athleisure: add shoes', 'score': 61},
      'primary_style': 'athleisure',
    });
    expect(look.primaryStyle, 'athleisure');
    expect(look.fitScore, isNotNull);
    expect(look.fitScore!.score, 61);
    expect(look.fitScore!.primaryStyle, 'athleisure');
    expect(look.fitScore!.criteria, hasLength(8));
    expect(look.score, 0.71);

    final old = CompleteLook.fromJson(const {
      'anchor_id': 'p', 'items': [], 'new_items_total_usd': 0.0, 'missing': [], 'score': 1.0,
    });
    expect(old.fitScore, isNull);
    expect(old.primaryStyle, isNull);
  });
}
