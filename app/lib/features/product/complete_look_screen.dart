import '../shared/niche_theme.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../closet/closet_screen.dart' show ownedClosetPhoto;

class CompleteLookScreen extends StatefulWidget {
  const CompleteLookScreen(
      {super.key,
      required this.api,
      required this.productId,
      required this.onProduct});
  final Api api;
  final String productId;
  final void Function(Product product) onProduct;
  @override
  State<CompleteLookScreen> createState() => _CompleteLookScreenState();
}

class _CompleteLookScreenState extends State<CompleteLookScreen> {
  FitScore? score;
  bool scoring = false;
  String? error;
  String? opening;
  Future<
      ({
        CompleteLook look,
        Map<String, ClosetItem> closet,
        Map<String, Product> catalog,
        bool photosUnavailable
      })> load() async {
    // Start both reads together; missing photos must not hide the recommendations.
    var photosUnavailable = false;
    final closetRead =
        widget.api.closet().then((items) => items, onError: (Object _) {
      photosUnavailable = true;
      return <ClosetItem>[];
    });
    final look = await widget.api.completeLook(widget.productId);
    final catalog = <String, Product>{};
    await Future.wait([
      for (final id in {
        for (final item in look.items)
          if (item.source == 'catalog' && item.id != null) item.id!
      })
        widget.api.product(id).then((p) {
          catalog[id] = p;
        }, onError: (Object _) {
          photosUnavailable = true;
        })
    ]);
    final closet = {for (final item in await closetRead) item.id: item};
    return (
      look: look,
      closet: closet,
      catalog: catalog,
      photosUnavailable: photosUnavailable
    );
  }

  Widget photo(LookItem item, Map<String, ClosetItem> closet,
      Map<String, Product> catalog) {
    final owned = closet[item.id];
    final url = item.source == 'closet'
        ? (owned == null ? '' : ownedClosetPhoto(owned))
        : (catalog[item.id]?.imageUrl ?? '');
    return SizedBox(
        width: 64,
        height: 80,
        child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: PiecePhoto(
                url: widget.api.imageProxyUrl(url), label: item.label)));
  }

  Future<void> rate(CompleteLook look) async {
    setState(() {
      scoring = true;
      error = null;
    });
    try {
      final result = await widget.api.fitScore(
        productIds: {
          widget.productId,
          for (final item in look.items)
            if (item.source == 'catalog' && item.id != null) item.id!
        }.toList(),
        targetStyle: look.primaryStyle,
        closetItemIds: [
          for (final item in look.items)
            if (item.source == 'closet' && item.id != null) item.id!
        ],
      );
      if (mounted) setState(() => score = result);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not score this look. Try again.');
      }
    } finally {
      if (mounted) setState(() => scoring = false);
    }
  }

  Future<void> open(LookItem item) async {
    setState(() {
      opening = item.id;
      error = null;
    });
    try {
      final product = await widget.api.product(item.id!);
      if (mounted) widget.onProduct(product);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not open this piece. Try again.');
      }
    } finally {
      if (mounted) setState(() => opening = null);
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Complete the look',
      child: AsyncContent(
        load: load,
        builder: (data) {
          final look = data.look;
          final displayedScore = score ?? look.fitScore;
          return ListView(padding: const EdgeInsets.all(20), children: [
            Text('Made to go together',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            const Text('Your closet first. Catalog suggestions fill the gaps.'),
            if (data.photosUnavailable)
              const Text(
                  'Some photos could not load. Reopen this look to retry.'),
            Text('New pieces · \$${look.newItemsTotalUsd.toStringAsFixed(2)}'),
            for (final item in look.items)
              Card(
                  child: ListTile(
                leading: photo(item, data.closet, data.catalog),
                minVerticalPadding: 16,
                title: Text(item.label),
                subtitle: Text(
                    '${item.source == 'closet' ? 'Already in your closet' : 'Catalog piece'} · ${item.category}${item.reason == null ? '' : '\n${item.reason}'}'),
                trailing: item.source == 'catalog' && item.id != null
                    ? TextButton(
                        onPressed: opening != null ? null : () => open(item),
                        child: Text(opening == item.id ? 'Opening…' : 'View'))
                    : null,
              )),
            if (look.missing.isNotEmpty)
              Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text('Still missing · ${look.missing.join(', ')}')),
            FilledButton.tonal(
                onPressed: scoring ? null : () => rate(look),
                child: Text(scoring ? 'Scoring…' : 'Get Fit Score')),
            if (error != null) Text(error!),
            if (displayedScore != null) fitScoreCard(displayedScore),
          ]);
        },
      ));
}

Widget fitScoreCard(FitScore score) {
  if (score.criteria.isEmpty) {
    return ScoreCard(
        score: score.score,
        verdict: score.verdict,
        notes: score.notes,
        breakdown: {
          'Color': '${score.breakdown.color}/40',
          'Pattern': '${score.breakdown.pattern}/20',
          'Formality': '${score.breakdown.formality}/20',
          'Completeness': '${score.breakdown.completeness}/20'
        });
  }
  final prefix = '${score.score} as ${score.primaryStyle}: ';
  final verdict = score.verdict.startsWith(prefix)
      ? score.verdict.substring(prefix.length)
      : score.verdict;
  return Builder(builder: (context) {
    final t = Niche.of(context);
    return Card(
        child: Padding(
            padding: const EdgeInsets.all(18),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Fit Score · ${score.score}/100',
                  style: Niche.display(24, 30, t.brand)),
              if (score.primaryStyle != null)
                Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: DecoratedBox(
                        decoration: BoxDecoration(
                            color: t.blush,
                            borderRadius: BorderRadius.circular(999)),
                        child: Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 5),
                            child: Text('As ${score.primaryStyle}',
                                style: Niche.ui(
                                    12, 16, FontWeight.w700, t.ink))))),
              const SizedBox(height: 10),
              Text(verdict, style: Niche.ui(14, 20, FontWeight.w500, t.ink)),
              const SizedBox(height: 14),
              for (final criterion in score.criteria)
                Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                              '${criterion.name[0].toUpperCase()}${criterion.name.substring(1)} · ${criterion.score10}/10',
                              style: Niche.ui(13, 18, FontWeight.w700, t.ink)),
                          const SizedBox(height: 6),
                          ClipRRect(
                              borderRadius: BorderRadius.circular(999),
                              child: LinearProgressIndicator(
                                  value: (criterion.score10 / 10)
                                      .clamp(0, 1)
                                      .toDouble(),
                                  minHeight: 6,
                                  backgroundColor: t.stone,
                                  color: t.brand)),
                          if (criterion.note != null)
                            Padding(
                                padding: const EdgeInsets.only(top: 6),
                                child: Text(criterion.note!,
                                    style: Niche.ui(
                                        13, 18, FontWeight.w500, t.muted))),
                        ])),
            ])));
  });
}
