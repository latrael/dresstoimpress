import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../store/store_controller.dart';
import '../closet/closet_screen.dart';

/// "Create 3 fits": outfits built only from the user's own closet (sprint 4). No shop pieces are
/// substituted, nothing is rendered on the body photo and nothing goes to the cart; the visual is a
/// board of the closet pieces themselves.
class FitsScreen extends StatefulWidget {
  const FitsScreen({super.key, required this.store, required this.onProduct});
  final StoreController store;
  final void Function(RankedProduct) onProduct;
  @override
  State<FitsScreen> createState() => _FitsScreenState();
}

class _FitsScreenState extends State<FitsScreen> {
  final occasionCtrl = TextEditingController();
  bool loading = false;
  String? error;
  List<OutfitFit> fits = [];

  @override
  void dispose() {
    occasionCtrl.dispose();
    super.dispose();
  }

  Future<void> generate() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final text = occasionCtrl.text.trim();
      final result = await widget.store.api
          .createFits(occasion: text.isEmpty ? null : text, count: 3);
      if (mounted) setState(() => fits = result);
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _openCloset() => Navigator.push<void>(context,
      MaterialPageRoute(builder: (_) => ClosetScreen(api: widget.store.api)));

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return FeaturePage(
        title: 'Fits from your closet',
        child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
            children: [
              const Text(
                  'Three outfits put together from what you already own.'),
              const SizedBox(height: 16),
              TextField(
                  key: const ValueKey('fits-occasion'),
                  controller: occasionCtrl,
                  enabled: !loading,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) =>
                      loading || widget.store.demo ? null : generate(),
                  decoration: const InputDecoration(
                      labelText: "What's the occasion?",
                      hintText: 'date night in SF, 55°F, walking a lot')),
              const SizedBox(height: 16),
              FilledButton.icon(
                  onPressed: loading || widget.store.demo ? null : generate,
                  icon: const Icon(NicheIcons.autoAwesome),
                  label: Text(loading ? 'Creating your fits…' : 'Create 3 fits')),
              if (widget.store.demo)
                const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('Connect your account to create fits.')),
              if (error != null)
                Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(error!),
                          TextButton(
                              onPressed: _openCloset,
                              child: const Text('Add to your closet')),
                        ])),
              if (!loading && fits.isEmpty && error == null)
                const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Text('Tell us the occasion to get started.')),
              for (final fit in fits)
                Card(
                    key: ValueKey('fit-${fit.id}'),
                    margin: const EdgeInsets.only(top: 20),
                    clipBehavior: Clip.antiAlias,
                    child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(fit.name, style: text.titleLarge),
                              const SizedBox(height: 4),
                              Text(fit.reason),
                              const SizedBox(height: 12),
                              _PieceBoard(
                                  pieces: fit.pieces,
                                  imageUrl: widget.store.imageUrl),
                              const SizedBox(height: 8),
                              for (final piece in fit.pieces)
                                ListTile(
                                    contentPadding: EdgeInsets.zero,
                                    dense: true,
                                    leading: const Icon(NicheIcons.checkroom),
                                    title: Text(piece.label),
                                    subtitle: Text(_slotName(piece.slot)),
                                    onTap: _openCloset),
                              if (fit.missing.isNotEmpty)
                                Padding(
                                    padding: const EdgeInsets.only(top: 8),
                                    child: Text(
                                        'Add ${fit.missing.map(_slotName).join(' and ')} to your closet to finish this one.',
                                        style: text.bodySmall)),
                            ]))),
            ]));
  }
}

String _slotName(String slot) => switch (slot) {
      'top' => 'top',
      'bottom' => 'bottoms',
      'shoes' => 'shoes',
      'outerwear' => 'a layer',
      'dress' => 'dress',
      'accessory' => 'accessory',
      _ => slot,
    };

/// The closet pieces of one fit as clean-shot tiles with their labels (never a composite image).
class _PieceBoard extends StatelessWidget {
  const _PieceBoard({required this.pieces, required this.imageUrl});
  final List<FitPiece> pieces;
  final String Function(String) imageUrl;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: .82,
        children: [
          for (final piece in pieces)
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                          width: double.infinity,
                          color: scheme.surfaceContainerHighest,
                          child: piece.imageUrl.isEmpty
                              ? const Center(child: Icon(NicheIcons.checkroom))
                              : Image.network(imageUrl(piece.imageUrl),
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) =>
                                      const Center(child: Icon(NicheIcons.checkroom)))))),
              const SizedBox(height: 6),
              Text(piece.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelMedium),
            ]),
        ]);
  }
}
