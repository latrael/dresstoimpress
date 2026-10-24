import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';

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
      child: AsyncContent<CompleteLook>(
        load: () => widget.api.completeLook(widget.productId),
        builder: (look) =>
            ListView(padding: const EdgeInsets.all(20), children: [
          Text('Made to go together',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('New pieces · \$${look.newItemsTotalUsd.toStringAsFixed(2)}'),
          for (final item in look.items)
            Card(
                child: ListTile(
              leading: Icon(item.source == 'closet'
                  ? Icons.checkroom
                  : Icons.shopping_bag_outlined),
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
          if (score != null) fitScoreCard(score!),
        ]),
      ));
}

Widget fitScoreCard(FitScore score) => ScoreCard(
        score: score.score,
        verdict: score.verdict,
        notes: score.notes,
        breakdown: {
          'Color': '${score.breakdown.color}/40',
          'Pattern': '${score.breakdown.pattern}/20',
          'Formality': '${score.breakdown.formality}/20',
          'Completeness': '${score.breakdown.completeness}/20',
        });
