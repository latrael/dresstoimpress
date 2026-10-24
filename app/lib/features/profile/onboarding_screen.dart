import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import 'shopper_profile.dart';
import 'body_scan_screen.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen(
      {super.key,
      required this.api,
      required this.onSaved,
      this.firstRun = false,
      this.demo = false});
  final bool firstRun, demo;
  final Api api;
  final Future<void> Function() onSaved;
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final name = TextEditingController();
  final text = TextEditingController();
  final measurements = {
    for (final label in [
      'Height (cm)',
      'Weight (kg)',
      'Waist (cm)',
      'Chest (cm)',
      'Hips (cm)',
      'Inseam (cm)',
      'Shoe size (US)'
    ])
      label: TextEditingController()
  };
  final budgets = {
    for (final category in ['tops', 'bottoms', 'jackets', 'shoes'])
      category: TextEditingController()
  };
  final usual = TextEditingController();
  String fit = 'regular';
  bool loading = true;
  @override
  void initState() {
    super.initState();
    restore();
  }

  Future<void> restore() async {
    var p = await ShopperProfile.load(widget.api.settings.userId);
    if (!widget.demo) {
      // Measurements saved on the server (another device, or a body scan) fill in what's missing here.
      try {
        final body = (await widget.api.getUser()).bodyProfile;
        if (body != null) p = p.withBody(body, gapsOnly: true);
      } catch (_) {}
    }
    if (!mounted) return;
    text.text = p.style;
    usual.text = p.usualSize;
    fit = p.fit;
    final values = [
      p.heightCm,
      p.weightKg,
      p.waistCm,
      p.chestCm,
      p.hipCm,
      p.inseamCm,
      p.shoeUs
    ];
    var i = 0;
    for (final c in measurements.values) {
      c.text = values[i++]?.toString() ?? '';
    }
    for (final e in budgets.entries) {
      e.value.text = p.budgets[e.key]?.toString() ?? '';
    }
    setState(() => loading = false);
  }

  OnboardingResult? result;
  String? error;
  bool busy = false;

  /// Body scan pre-fills the measurement fields (council D2: the user checks them, then saves).
  Future<void> scanBody() async {
    final body = await Navigator.push<BodyProfile>(
        context,
        MaterialPageRoute(
            builder: (_) => BodyScanScreen(
                api: widget.api,
                heightCm:
                    double.tryParse(measurements['Height (cm)']!.text.trim()),
                weightKg: double.tryParse(
                    measurements['Weight (kg)']!.text.trim()))));
    if (body == null || !mounted) return;
    double? cm(double? inches) => inches == null ? null : inches * 2.54;
    final values = {
      'Height (cm)': body.heightCm > 0 ? body.heightCm : null,
      'Weight (kg)': body.weightKg,
      'Waist (cm)': cm(body.waistIn),
      'Chest (cm)': cm(body.chestIn),
      'Hips (cm)': cm(body.hipIn),
      'Inseam (cm)': cm(body.inseamIn),
    };
    setState(() {
      for (final e in values.entries) {
        if (e.value != null) {
          measurements[e.key]!.text = e.value!.toStringAsFixed(1);
        }
      }
      error = null;
    });
  }
  @override
  void dispose() {
    for (final c in [...measurements.values, ...budgets.values, usual]) {
      c.dispose();
    }
    name.dispose();
    text.dispose();
    super.dispose();
  }

  Future<void> save({bool skip = false}) async {
    double? number(String label) =>
        skip ? null : double.tryParse(measurements[label]!.text.trim());
    if (!skip &&
        [...measurements.values, ...budgets.values].any((c) =>
            c.text.trim().isNotEmpty &&
            (double.tryParse(c.text.trim()) == null ||
                !double.parse(c.text.trim()).isFinite ||
                double.parse(c.text.trim()) <= 0))) {
      setState(() => error =
          'Use positive numbers for measurements and prices, or leave them blank.');
      return;
    }
    final profile = ShopperProfile(
        completed: true,
        style: skip ? '' : text.text.trim(),
        fit: fit,
        usualSize: skip ? '' : usual.text.trim().toUpperCase(),
        heightCm: number('Height (cm)'),
        weightKg: number('Weight (kg)'),
        waistCm: number('Waist (cm)'),
        chestCm: number('Chest (cm)'),
        hipCm: number('Hips (cm)'),
        inseamCm: number('Inseam (cm)'),
        shoeUs: number('Shoe size (US)'),
        budgets: {
          if (!skip)
            for (final e in budgets.entries)
              if (e.value.text.trim().isNotEmpty)
                e.key: double.parse(e.value.text.trim())
        });
    setState(() {
      busy = true;
      error = null;
      result = null;
    });
    try {
      final priceText = profile.budgets.entries
          .map((e) => '${e.key} under \$${e.value}')
          .join(', ');
      final input = [
        profile.style,
        if (profile.style.isNotEmpty) '${profile.fit} fit',
        priceText
      ].where((s) => s.isNotEmpty).join(', ');
      if (!widget.demo && !skip && input.isNotEmpty) {
        final saved = await widget.api.onboarding(input,
            displayName: name.text.trim().isEmpty ? null : name.text.trim());
        if (!mounted) return;
        setState(() => result = saved);
      }
      await profile.save(widget.api.settings.userId);
      if (!widget.demo && !skip) {
        // D5: measurements live on the server too. Best effort: the phone copy is already saved.
        try {
          await profile.syncToServer(widget.api);
        } catch (_) {}
      }
      await widget.onSaved();
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not save your preferences. Try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: widget.firstRun ? 'Welcome to Niche' : 'Your style & sizing',
      child: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(24), children: [
              Text('Make it feel like you',
                  style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 12),
              const Text(
                  'Start with your style, your measurements, or both. Everything is optional and you can change it later.'),
              const SizedBox(height: 20),
              TextField(
                  controller: name,
                  enabled: !busy,
                  decoration: const InputDecoration(
                      labelText: 'Display name (optional)')),
              const SizedBox(height: 16),
              TextField(
                  controller: text,
                  enabled: !busy,
                  minLines: 3,
                  maxLines: 6,
                  decoration: const InputDecoration(
                      labelText: 'Style and budget',
                      hintText:
                          'Baggy streetwear, relaxed fits, Uniqlo, earth tones…')),
              const SizedBox(height: 24),
              Text('Your fit', style: Theme.of(context).textTheme.titleLarge),
              const Text(
                  'Enter your measurements, or scan a full-body photo to fill them in. Check the estimates before saving.'),
              if (!widget.demo)
                Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                        onPressed: busy ? null : scanBody,
                        icon: const Icon(Icons.accessibility_new),
                        label: const Text('Scan from a photo'))),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                  initialValue: fit,
                  decoration: const InputDecoration(labelText: 'Preferred fit'),
                  items: [
                    for (final v in ['slim', 'regular', 'oversized'])
                      DropdownMenuItem(value: v, child: Text(v))
                  ],
                  onChanged: busy ? null : (v) => setState(() => fit = v!)),
              for (final e in measurements.entries)
                Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: TextField(
                        controller: e.value,
                        enabled: !busy,
                        keyboardType: const TextInputType.numberWithOptions(
                            decimal: true),
                        decoration: InputDecoration(labelText: e.key))),
              const SizedBox(height: 12),
              TextField(
                  controller: usual,
                  enabled: !busy,
                  decoration: const InputDecoration(
                      labelText: 'Usual letter size (optional)',
                      hintText: 'XS, S, M, L, XL…')),
              const SizedBox(height: 24),
              Text('Your price range',
                  style: Theme.of(context).textTheme.titleLarge),
              const Text('Optional — leave any category blank to skip it.'),
              for (final e in budgets.entries)
                Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: TextField(
                        controller: e.value,
                        enabled: !busy,
                        keyboardType: const TextInputType.numberWithOptions(
                            decimal: true),
                        decoration: InputDecoration(
                            labelText: 'Maximum for ${e.key} (USD)'))),
              const SizedBox(height: 20),
              FilledButton(
                  onPressed: busy ? null : () => save(),
                  child: Text(busy
                      ? 'Saving…'
                      : widget.firstRun
                          ? 'Start browsing'
                          : 'Save preferences')),
              if (widget.firstRun)
                TextButton(
                    onPressed: busy ? null : () => save(skip: true),
                    child: const Text('Skip for now')),
              if (error != null) Text(error!),
              if (result != null) ...[
                const SizedBox(height: 20),
                Text('Saved for ${result!.user.displayName}',
                    style: Theme.of(context).textTheme.titleLarge),
                Text(result!.styles.isEmpty
                    ? 'No style tags recognized.'
                    : 'Styles · ${result!.styles.join(', ')}'),
                for (final e in result!.user.priceRanges.entries)
                  if (e.value.length >= 2)
                    Text(
                        '${e.key} · \$${e.value[0].toStringAsFixed(0)}–\$${e.value[1].toStringAsFixed(0)}'),
                if (result!.unmatched.isNotEmpty)
                  Text('Not understood yet · ${result!.unmatched}'),
                const Text(
                    'You can update this any time. Your suggestions have been refreshed.'),
              ],
            ]));
}
