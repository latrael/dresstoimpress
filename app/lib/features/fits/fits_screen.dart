import 'package:flutter/material.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../store/store_controller.dart';
import '../closet/closet_screen.dart';

String _retailerName(String retailer) => retailer == 'hm'
    ? 'H&M'
    : retailer == 'uniqlo'
        ? 'Uniqlo'
        : retailer;
String _dollars(num value) => '\$${value.toStringAsFixed(2)}';

class FitsScreen extends StatefulWidget {
  const FitsScreen({super.key, required this.store, required this.onProduct});
  final StoreController store;
  final void Function(RankedProduct) onProduct;
  @override
  State<FitsScreen> createState() => _FitsScreenState();
}

class _FitsScreenState extends State<FitsScreen> {
  String occasion = 'everyday';
  bool loading = false;
  String? error;
  List<OutfitFit> fits = [];
  final working = <String>{};
  final previews = <String, ({String url, String mode})>{};
  final messages = <String, String>{};
  Future<void> generate() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result =
          await widget.store.api.createFits(occasion: occasion, count: 3);
      if (mounted) {
        setState(() {
          fits = result;
          previews.clear();
          messages.clear();
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> action(OutfitFit fit, {required bool cart}) async {
    if (working.contains(fit.id)) return;
    setState(() {
      working.add(fit.id);
      messages.remove(fit.id);
    });
    try {
      if (cart) {
        await widget.store.api.addFitToCart(fit.id);
        await widget.store.refreshCart();
        if (mounted) {
          setState(() => messages[fit.id] =
              'New pieces added. Review sizes in your cart.');
        }
      } else {
        final result = await widget.store.api.fitTryOn(fit.id);
        if (mounted) {
          setState(() => previews[fit.id] =
              (url: result.imageUrl, mode: result.mode ?? 'unknown'));
        }
      }
    } catch (e) {
      if (mounted) setState(() => messages[fit.id] = featureError(e));
    } finally {
      if (mounted) setState(() => working.remove(fit.id));
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Fits for you',
      child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
          children: [
            const Text(
                'Outfits built around your style, size and closet. Only new pieces go into your cart.'),
            const SizedBox(height: 16),
            Wrap(spacing: 8, children: [
              for (final choice in [
                'everyday',
                'class',
                'date',
                'rooftop party'
              ])
                ChoiceChip(
                    label: Text(choice),
                    selected: occasion == choice,
                    onSelected: loading
                        ? null
                        : (_) => setState(() => occasion = choice))
            ]),
            const SizedBox(height: 16),
            FilledButton.icon(
                onPressed: loading || working.isNotEmpty || widget.store.demo
                    ? null
                    : generate,
                icon: const Icon(Icons.auto_awesome),
                label: Text(loading ? 'Creating your fits…' : 'Create 3 fits')),
            if (widget.store.demo)
              const Padding(
                  padding: EdgeInsets.all(12),
                  child:
                      Text('Connect your account to create personal outfits.')),
            if (error != null)
              Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
            if (!loading && fits.isEmpty && error == null)
              const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Text('Choose an occasion to get started.')),
            for (final fit in fits)
              Card(
                  margin: const EdgeInsets.only(top: 20),
                  child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(fit.name,
                                style: Theme.of(context).textTheme.titleLarge),
                            Text(fit.reason),
                            for (final piece in fit.pieces)
                              ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading: piece.imageUrl.isEmpty
                                      ? const Icon(Icons.checkroom)
                                      : Image.network(
                                          widget.store.imageUrl(piece.imageUrl),
                                          width: 52,
                                          height: 64,
                                          fit: BoxFit.cover,
                                          errorBuilder: (_, __, ___) =>
                                              const Icon(Icons.checkroom)),
                                  title: Text(piece.label),
                                  subtitle: Text(piece.fromCloset
                                      ? 'In your closet'
                                      : '${_retailerName(piece.product?.retailer ?? '')} · ${piece.yourSize == null ? 'Review size' : 'Size ${piece.yourSize}'}${piece.inYourSize == false ? ' · alternative fit' : ''}'),
                                  onTap: () {
                                    if (piece.fromCloset) {
                                      Navigator.push<void>(
                                          context,
                                          MaterialPageRoute(
                                              builder: (_) => ClosetScreen(
                                                  api: widget.store.api)));
                                    } else if (piece.product != null) {
                                      widget.onProduct(RankedProduct(
                                          product: piece.product!,
                                          yourSize: piece.yourSize,
                                          inYourSize: piece.inYourSize));
                                    }
                                  }),
                            Text(
                                '${fit.closetCount} from your closet · New pieces ${_dollars(fit.newTotalUsd)}',
                                style: const TextStyle(
                                    fontWeight: FontWeight.w600)),
                            if (previews[fit.id] != null ||
                                fit.tryOnUrl != null) ...[
                              const SizedBox(height: 12),
                              Text((previews[fit.id]?.mode ?? fit.tryOnMode) ==
                                      'collage'
                                  ? 'Outfit board — not a photo of you'
                                  : 'Your virtual try-on'),
                              Image.network(
                                  widget.store.imageUrl(
                                      previews[fit.id]?.url ?? fit.tryOnUrl!),
                                  height: 340,
                                  fit: BoxFit.contain,
                                  errorBuilder: (_, __, ___) => const Text(
                                      'Preview could not load. Try again.')),
                            ],
                            if (messages[fit.id] != null)
                              Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 12),
                                  child: Text(messages[fit.id]!)),
                            Wrap(spacing: 8, children: [
                              OutlinedButton(
                                  onPressed: working.contains(fit.id)
                                      ? null
                                      : () => action(fit, cart: false),
                                  child: Text(working.contains(fit.id)
                                      ? 'Working…'
                                      : 'Try on this fit')),
                              FilledButton(
                                  onPressed: working.contains(fit.id)
                                      ? null
                                      : () => action(fit, cart: true),
                                  child: const Text('Add fit to cart')),
                            ]),
                          ]))),
          ]));
}
