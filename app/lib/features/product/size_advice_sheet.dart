import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';

Future<String?> showSizeAdvice(
        BuildContext context, Api api, String productId) =>
    showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => SizeAdviceSheet(api: api, productId: productId),
    );

class SizeAdviceSheet extends StatefulWidget {
  const SizeAdviceSheet(
      {super.key, required this.api, required this.productId});
  final Api api;
  final String productId;
  @override
  State<SizeAdviceSheet> createState() => _SizeAdviceSheetState();
}

class _SizeAdviceSheetState extends State<SizeAdviceSheet> {
  late final height =
      TextEditingController(text: '${widget.api.settings.heightCm}');
  late final weight =
      TextEditingController(text: '${widget.api.settings.weightKg}');
  final waist = TextEditingController();
  final shoe = TextEditingController();
  String fit = 'regular';
  SizeAdvice? advice;
  String? error;
  bool busy = false;
  @override
  void dispose() {
    height.dispose();
    weight.dispose();
    waist.dispose();
    shoe.dispose();
    super.dispose();
  }

  Future<void> recommend() async {
    final h = double.tryParse(height.text), w = double.tryParse(weight.text);
    final waistValue = double.tryParse(waist.text),
        shoeValue = double.tryParse(shoe.text);
    if (h == null ||
        !h.isFinite ||
        h <= 0 ||
        w == null ||
        !w.isFinite ||
        w <= 0 ||
        (waist.text.isNotEmpty &&
            (waistValue == null || !waistValue.isFinite || waistValue <= 0)) ||
        (shoe.text.isNotEmpty &&
            (shoeValue == null || !shoeValue.isFinite || shoeValue <= 0))) {
      setState(() => error =
          'Enter positive measurements. Waist and shoe size are optional.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
      advice = null;
    });
    try {
      final result = await widget.api.sizeAdvice(widget.productId,
          heightCm: h,
          weightKg: w,
          fit: fit,
          waistIn: waistValue,
          shoeUs: shoeValue);
      if (mounted) setState(() => advice = result);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not get a recommendation. Try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(
            24, 20, 24, 24 + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
            child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              Text('Find your size',
                  style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              const Text(
                  'A starting point for this piece, based on your measurements. Review the fit before adding it.'),
              const SizedBox(height: 16),
              for (final field in [
                (height, 'Height (cm)'),
                (weight, 'Weight (kg)'),
                (waist, 'Waist (inches, optional)'),
                (shoe, 'US shoe size (optional)')
              ])
                Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: TextField(
                        controller: field.$1,
                        enabled: !busy,
                        keyboardType: const TextInputType.numberWithOptions(
                            decimal: true),
                        decoration: InputDecoration(labelText: field.$2))),
              DropdownButtonFormField<String>(
                  initialValue: fit,
                  decoration: const InputDecoration(labelText: 'Preferred fit'),
                  items: [
                    for (final f in ['slim', 'regular', 'oversized'])
                      DropdownMenuItem(value: f, child: Text(f))
                  ],
                  onChanged: busy ? null : (f) => setState(() => fit = f!)),
              const SizedBox(height: 16),
              FilledButton(
                  onPressed: busy ? null : recommend,
                  child: Text(busy ? 'Finding your size…' : 'Recommend size')),
              if (error != null)
                Text(error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error)),
              if (advice != null) ...[
                const SizedBox(height: 16),
                Text(
                    advice!.size == null
                        ? 'No size recommendation available'
                        : 'Suggested size ${advice!.size}',
                    style: Theme.of(context).textTheme.titleLarge),
                Text('${advice!.confidence} confidence'),
                Text(advice!.reason),
                if (advice!.size != null)
                  TextButton(
                      onPressed: () => Navigator.pop(context, advice!.size),
                      child: const Text('Select this size')),
              ],
            ])),
      );
}
