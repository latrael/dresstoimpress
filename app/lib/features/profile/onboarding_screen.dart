import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';
import 'shopper_profile.dart';
import 'measurement_picker.dart';
import '../shared/store_names.dart';

/// The same sections power first-time setup and the User editor.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen(
      {super.key,
      required this.api,
      required this.onSaved,
      this.firstRun = false,
      this.demo = false,
      this.initialStep = 1,
      this.picker,
      this.onConnect});
  final Api api;
  final Future<void> Function() onSaved;
  final bool firstRun, demo;
  final int initialStep;
  final PhotoPicker? picker;
  final Future<bool> Function()? onConnect;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  static const titles = [
    'Welcome to Niche',
    'Your style',
    'Stores you like',
    'Body scan',
    'Measurements & size',
    'Your budget',
    'Ready for you',
    'Shop for'
  ];
  final name = TextEditingController(),
      style = TextEditingController(),
      other = TextEditingController();
  final measures = {
    for (final s in [
      'Height (cm)',
      'Weight (kg)',
      'Chest (cm)',
      'Waist (cm)',
      'Hips (cm)',
      'Inseam (cm)',
      'Shoe size (US)'
    ])
      s: TextEditingController()
  };
  final sizes = {
    for (final s in ['top', 'bottom', 'shoes']) s: TextEditingController()
  };
  final budgets = {
    for (final s in ['tops', 'bottoms', 'jackets', 'shoes'])
      s: TextEditingController()
  };
  final stores = <String>{};
  bool loadedRemote = false;
  final restoredMeasures = <String, double?>{};
  late bool demo = widget.demo;
  Future<void> connectInline() async {
    bool connected;
    try {
      connected = await widget.onConnect?.call() ?? false;
    } catch (_) {
      connected = false;
    }
    if (mounted) {
      setState(() {
        demo = !connected;
        error = connected
            ? null
            : 'Connection is not ready. Check your settings and retry.';
      });
    }
  }

  late int step = widget.firstRun ? 0 : widget.initialStep;
  String fit = 'regular';
  String shopFor = 'both';
  final preScan = <String, String>{};
  final filledByScan = <String, String>{};
  final styles = <String>{};
  static const styleChoices = [
    'minimalist',
    'classic',
    'streetwear',
    'athleisure',
    'y2k',
    'preppy',
    'vintage',
    'grunge',
    'business',
    'boho',
    'clean girl',
    'old money',
    'gorpcore'
  ];
  bool loading = true, busy = false, restoreFailed = false;
  String? error;
  BodyScanResult? scan;
  OnboardingResult? result;
  @override
  void initState() {
    super.initState();
    restore();
  }

  @override
  void dispose() {
    for (final c in [
      name,
      style,
      other,
      ...measures.values,
      ...sizes.values,
      ...budgets.values
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> restore() async {
    try {
      restoreFailed = false;
      final local = await ShopperProfile.load(widget.api.settings.userId);
      BodyProfile? remote;
      AppUser? user;
      if (!demo) {
        user = await widget.api.getUser();
        remote = user.bodyProfile;
        loadedRemote = true;
      }
      if (!mounted) return;
      name.text = user?.displayName ?? '';
      final ownWords = <String>[];
      for (final token in (user?.styleText ?? local.style).split(',')) {
        final clean = token.trim();
        if (styleChoices.contains(clean.toLowerCase())) {
          styles.add(clean.toLowerCase());
        } else if (clean.isNotEmpty) {
          ownWords.add(clean);
        }
      }
      style.text = ownWords.join(', ');
      fit = remote?.fit ?? local.fit;
      shopFor = user?.shopFor ?? local.shopFor;
      stores.addAll((user?.preferredStores ?? local.preferredStores)
          .where((s) => storeNames.containsKey(s)));
      other.text = user == null
          ? local.otherStores
          : user.preferredStores
              .where((s) => !storeNames.containsKey(s))
              .join(', ');
      final values = [
        remote?.heightCm ?? local.heightCm,
        remote?.weightKg ?? local.weightKg,
        remote?.chestIn == null ? local.chestCm : remote!.chestIn! * 2.54,
        remote?.waistIn == null ? local.waistCm : remote!.waistIn! * 2.54,
        remote?.hipIn == null ? local.hipCm : remote!.hipIn! * 2.54,
        remote?.inseamIn == null ? local.inseamCm : remote!.inseamIn! * 2.54,
        remote?.shoeUs ?? local.shoeUs
      ];
      var i = 0;
      for (final c in measures.values) {
        c.text = values[i++]?.toStringAsFixed(1) ?? '';
      }
      restoredMeasures.clear();
      restoredMeasures.addAll({
        for (final e in measures.entries) e.key: double.tryParse(e.value.text)
      });
      for (final e in sizes.entries) {
        e.value.text = remote?.usualSizes[e.key] ??
            local.usualSizes[e.key] ??
            (e.key == 'top' ? local.usualSize : '');
      }
      for (final e in budgets.entries) {
        final server = user?.priceRanges[{
          'tops': 'top',
          'bottoms': 'bottom',
          'jackets': 'outerwear',
          'shoes': 'shoes'
        }[e.key]];
        e.value.text = (server != null && server.length > 1
                    ? server[1]
                    : local.budgets[e.key])
                ?.toString() ??
            '';
      }
    } catch (_) {
      if (mounted) {
        error =
            'Could not load your saved answers. Retry before making changes.';
        restoreFailed = true;
      }
    }
    if (mounted) setState(() => loading = false);
  }

  double? value(String label) => double.tryParse(measures[label]!.text.trim());
  bool validate(Iterable<TextEditingController> fields) {
    if (fields.any((c) =>
        c.text.trim().isNotEmpty &&
        (double.tryParse(c.text.trim()) == null ||
            !double.parse(c.text.trim()).isFinite ||
            double.parse(c.text.trim()) <= 0))) {
      setState(() =>
          error = 'Use positive numbers, or leave optional fields blank.');
      return false;
    }
    return true;
  }

  Future<void> scanBody() async {
    final height = value('Height (cm)'), weight = value('Weight (kg)');
    if (height == null ||
        height < 120 ||
        height > 230 ||
        (weight != null && (weight < 30 || weight > 250))) {
      setState(() => error =
          'Choose your height first (about 4–7½ ft). Weight is optional (66–550 lb).');
      return;
    }
    if (demo) {
      setState(() => error =
          'Connect to use a private body scan. You can enter measurements on the next screen.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final photo = await (widget.picker != null
          ? widget.picker!()
          : choosePhoto(context));
      if (photo == null) return;
      final estimate = await widget.api.bodyScan(photo.bytes,
          heightCm: height,
          weightKg: weight,
          mimeType: photo.mimeType,
          commit: false);
      if (!mounted) return;
      for (final e in filledByScan.entries) {
        if (measures[e.key]!.text == e.value) {
          measures[e.key]!.text = preScan[e.key] ?? '';
        }
      }
      preScan.clear();
      preScan.addAll({for (final e in measures.entries) e.key: e.value.text});
      filledByScan.clear();
      final p = estimate.profile;
      final estimates = {
        'Chest (cm)': p.chestIn,
        'Waist (cm)': p.waistIn,
        'Hips (cm)': p.hipIn,
        'Inseam (cm)': p.inseamIn
      };
      for (final e in estimates.entries) {
        if (measures[e.key]!.text.trim().isEmpty && e.value != null) {
          measures[e.key]!.text = (e.value! * 2.54).toStringAsFixed(1);
          filledByScan[e.key] = measures[e.key]!.text;
        }
      }
      setState(() => scan = estimate);
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void discardScan() => setState(() {
        for (final e in filledByScan.entries) {
          if (measures[e.key]!.text == e.value) {
            measures[e.key]!.text = preScan[e.key] ?? '';
          }
        }
        scan = null;
        filledByScan.clear();
      });
  void skip() {
    if ((step == 3 || step == 4) && scan != null) discardScan();
    setState(() {
      step = step == 1
          ? 7
          : step == 7
              ? 2
              : step + 1;
      error = null;
    });
  }

  Future<void> saveMeasurements(ShopperProfile profile) async {
    final draft = scan;
    if (draft == null) {
      if (!loadedRemote) {
        await profile.syncToServer(widget.api);
        return;
      }
      double? changed(String field) {
        final current = value(field), old = restoredMeasures[field];
        if (old != null && current == null) {
          throw Exception(
              'Choose a value for your saved measurement. Clearing saved measurements is not available yet.');
        }
        return current != null && (old == null || (current - old).abs() > .06)
            ? current
            : null;
      }

      await widget.api.updateBodyProfile(
          heightCm: changed('Height (cm)'),
          weightKg: changed('Weight (kg)'),
          chestCm: changed('Chest (cm)'),
          waistCm: changed('Waist (cm)'),
          hipCm: changed('Hips (cm)'),
          inseamCm: changed('Inseam (cm)'),
          shoeUs: changed('Shoe size (US)'),
          fit: fit,
          usualSizes: profile.usualSizes);
      return;
    }
    final p = draft.profile;
    final baseline = <String, double?>{
      'Height (cm)': p.heightCm,
      'Weight (kg)': p.weightKg,
      'Chest (cm)': p.chestIn == null ? null : p.chestIn! * 2.54,
      'Waist (cm)': p.waistIn == null ? null : p.waistIn! * 2.54,
      'Hips (cm)': p.hipIn == null ? null : p.hipIn! * 2.54,
      'Inseam (cm)': p.inseamIn == null ? null : p.inseamIn! * 2.54,
      'Shoe size (US)': p.shoeUs
    };
    double? edit(String field, {bool inches = false}) {
      final v = value(field), old = baseline[field];
      if (v == null && old != null) {
        throw Exception(
            'Discard this scan to skip its estimates, or review a value before saving.');
      }
      return v != null && (old == null || (v - old).abs() > .06)
          ? (inches ? v / 2.54 : v)
          : null;
    }

    scan = await widget.api.confirmBodyScan(draft,
        heightCm: edit('Height (cm)'),
        weightKg: edit('Weight (kg)'),
        chestIn: edit('Chest (cm)', inches: true),
        waistIn: edit('Waist (cm)', inches: true),
        hipIn: edit('Hips (cm)', inches: true),
        inseamIn: edit('Inseam (cm)', inches: true),
        shoeUs: edit('Shoe size (US)'),
        fit: p.fit == fit ? null : fit);
    // Keep unchanged estimates as estimates; only preferences go through the manual endpoint.
    await widget.api
        .updateBodyProfile(fit: fit, usualSizes: profile.usualSizes);
  }

  Future<void> save({bool skipAll = false}) async {
    if (restoreFailed && !skipAll) return;
    if (!skipAll && !validate([...measures.values, ...budgets.values])) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final profile = ShopperProfile(
          completed: true,
          style: skipAll
              ? ''
              : [...styles, style.text.trim()]
                  .where((s) => s.isNotEmpty)
                  .join(', '),
          fit: fit,
          shopFor: shopFor,
          preferredStores: skipAll ? [] : stores.toList(),
          otherStores: skipAll ? '' : other.text.trim(),
          usualSize: skipAll ? '' : sizes['top']!.text.trim().toUpperCase(),
          usualSizes: {
            if (!skipAll)
              for (final e in sizes.entries)
                if (e.value.text.trim().isNotEmpty)
                  e.key: e.value.text.trim().toUpperCase()
          },
          heightCm: skipAll ? null : value('Height (cm)'),
          weightKg: skipAll ? null : value('Weight (kg)'),
          chestCm: skipAll ? null : value('Chest (cm)'),
          waistCm: skipAll ? null : value('Waist (cm)'),
          hipCm: skipAll ? null : value('Hips (cm)'),
          inseamCm: skipAll ? null : value('Inseam (cm)'),
          shoeUs: skipAll ? null : value('Shoe size (US)'),
          budgets: {
            if (!skipAll)
              for (final e in budgets.entries)
                if (e.value.text.trim().isNotEmpty)
                  e.key: double.parse(e.value.text.trim())
          });
      if (!demo && !skipAll) {
        final input = [
          profile.style,
          if (profile.style.isNotEmpty) '${profile.fit} fit',
          if (stores.isNotEmpty) 'Preferred stores: ${stores.join(', ')}',
          if (other.text.trim().isNotEmpty)
            'Other store interests: ${other.text.trim()}',
          ...profile.budgets.entries.map((e) => '${e.key} under \$${e.value}')
        ].where((s) => s.isNotEmpty).join(', ');
        if (input.isNotEmpty) {
          result = await widget.api.onboarding(input,
              displayName: name.text.trim().isEmpty ? null : name.text.trim());
        }
        await saveMeasurements(profile);
        await widget.api.updateUser(
            displayName: name.text.trim().isEmpty ? null : name.text.trim(),
            shopFor: shopFor,
            preferredStores: [
              ...profile.preferredStores,
              ...profile.otherStores
                  .split(',')
                  .map((s) => s.trim())
                  .where((s) => s.isNotEmpty)
            ],
            onboarded: widget.firstRun ? true : null,
            priceRanges: widget.firstRun || step == 5
                ? {
                    for (final e in profile.budgets.entries)
                      ({
                            'tops': 'top',
                            'bottoms': 'bottom',
                            'jackets': 'outerwear',
                            'shoes': 'shoes'
                          }[e.key] ??
                          e.key): [0, e.value]
                  }
                : null);
      }
      if (!demo && skipAll) await widget.api.updateUser(onboarded: true);
      await profile.save(widget.api.settings.userId);
      await widget.onSaved();
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) {
        setState(() =>
            error = 'Could not save all your answers. ${featureError(e)}');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget measurement(String key) => MeasurementPicker(
      kind: key,
      value: value(key),
      enabled: !busy,
      onChanged: (v) =>
          setState(() => measures[key]!.text = v?.toString() ?? ''));

  Widget field(TextEditingController controller, String label,
          {bool number = false, String? hint}) =>
      Padding(
          padding: const EdgeInsets.only(top: 14),
          child: TextField(
              controller: controller,
              enabled: !busy,
              keyboardType: number
                  ? const TextInputType.numberWithOptions(decimal: true)
                  : TextInputType.text,
              decoration: InputDecoration(labelText: label, hintText: hint)));
  List<Widget> section() {
    switch (step) {
      case 0:
        return [
          Text("Let's make Niche yours",
              style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 16),
          const Text(
              'Tell us your style, stores and fit once. Every optional step can be skipped.')
        ];
      case 1:
        return [
          const Text(
              'Describe the looks you want, fits you love, and anything you hate wearing.'),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 6, children: [
            for (final choice in styleChoices)
              FilterChip(
                  label: Text(choice),
                  selected: styles.contains(choice),
                  onSelected: busy
                      ? null
                      : (v) => setState(() {
                            v ? styles.add(choice) : styles.remove(choice);
                          }))
          ]),
          field(name, 'Display name (optional)'),
          field(style, 'Type your own (optional)',
              hint: 'Y2K fits, baggy jeans, no skinny anything…')
        ];
      case 7:
        return [
          const Text('Which clothing would you like to browse?'),
          const SizedBox(height: 16),
          Wrap(spacing: 8, children: [
            for (final e
                in {'men': 'Men', 'women': 'Women', 'both': 'Both'}.entries)
              ChoiceChip(
                  label: Text(e.value),
                  selected: shopFor == e.key,
                  onSelected:
                      busy ? null : (_) => setState(() => shopFor = e.key))
          ]),
        ];
      case 2:
        return [
          const Text('Stores we carry'),
          const SizedBox(height: 12),
          Wrap(spacing: 8, children: [
            for (final e in storeNames.entries)
              FilterChip(
                  label: Text(e.value),
                  selected: stores.contains(e.key),
                  onSelected: busy
                      ? null
                      : (selected) => setState(() {
                            selected ? stores.add(e.key) : stores.remove(e.key);
                          }))
          ]),
          field(other, 'Other stores you love (optional)'),
          const SizedBox(height: 12),
          const Text(
              'Other stores are saved as interests. Choose your favorites from the current catalog above.')
        ];
      case 3:
        return [
          const Text(
              'A full-body photo helps estimate your proportions. Enter your height as a reference. Your photo stays private and is also used for try-on.'),
          measurement('Height (cm)'),
          measurement('Weight (kg)'),
          const SizedBox(height: 20),
          if (demo && widget.onConnect != null)
            OutlinedButton.icon(
                onPressed: connectInline,
                icon: const Icon(Icons.link),
                label: const Text('Connect for a private scan')),
          FilledButton.tonalIcon(
              onPressed: busy ? null : scanBody,
              icon: const Icon(Icons.add_a_photo_outlined),
              label: Text(busy ? 'Estimating…' : 'Choose a full-body photo')),
          if (scan != null) ...[
            const SizedBox(height: 16),
            Text(scan!.profile.source == 'ai'
                ? 'Estimates from your photo — review every value next.'
                : 'Estimated proportions — review every value next.'),
            if (scan!.profile.fullBody == false)
              const Text(
                  'Please retake with one person visible from head to feet.'),
            Text(scan!.profile.note),
            Text(scan!.committed
                ? 'This scan has been saved to your profile.'
                : 'This scan is a draft until you save your reviewed measurements.'),
            if (!scan!.committed)
              TextButton(
                  onPressed: busy ? null : discardScan,
                  child: const Text('Discard scan'))
          ]
        ];
      case 4:
        return [
          if (scan != null && !scan!.committed)
            TextButton(
                onPressed: busy ? null : discardScan,
                child: const Text('Discard scan')),
          const Text(
              'Check or edit every measurement. Photo estimates are a starting point, not an exact measurement.'),
          for (final e in measures.entries) measurement(e.key),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
              initialValue: fit,
              decoration: const InputDecoration(labelText: 'Preferred fit'),
              items: [
                for (final v in ['slim', 'regular', 'oversized'])
                  DropdownMenuItem(value: v, child: Text(v))
              ],
              onChanged: busy ? null : (v) => setState(() => fit = v!)),
          for (final e in sizes.entries)
            field(e.value, 'Usual ${e.key} size (optional)',
                hint: e.key == 'top'
                    ? 'XS, S, M, L…'
                    : e.key == 'bottom'
                        ? '32/32, M…'
                        : '9, 10…')
        ];
      case 5:
        return [
          const Text('Optional — leave any category blank to skip it.'),
          for (final e in budgets.entries)
            field(e.value, 'Maximum for ${e.key} (USD)', number: true)
        ];
      default:
        return [
          Text('Your feed is ready',
              style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 16),
          const Text(
              'Your style, stores, measurements and budgets can all be changed later under User.')
        ];
    }
  }

  void next() {
    if ((step == 3 || step == 4) && !validate(measures.values)) return;
    if (step == 5 && !validate(budgets.values)) return;
    setState(() {
      step = step == 1
          ? 7
          : step == 7
              ? 2
              : step + 1;
      error = null;
    });
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: titles[step],
      child: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              key: ValueKey('onboarding-$step'),
              padding: const EdgeInsets.all(24),
              children: [
                  if (widget.firstRun)
                    Padding(
                        padding: const EdgeInsets.only(bottom: 20),
                        child: LinearProgressIndicator(
                            value:
                                ([0, 1, 7, 2, 3, 4, 5, 6].indexOf(step) + 1) /
                                    8)),
                  ...section(),
                  const SizedBox(height: 24),
                  if (error != null)
                    Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(error!,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.error))),
                  if (restoreFailed)
                    TextButton(
                        onPressed: busy
                            ? null
                            : () async {
                                setState(() => loading = true);
                                await restore();
                              },
                        child: const Text('Retry loading answers')),
                  FilledButton(
                      onPressed: busy || restoreFailed
                          ? null
                          : !widget.firstRun && step == 3
                              ? () => setState(() => step = 4)
                              : !widget.firstRun || step == 6
                                  ? () => save()
                                  : next,
                      child: Text(busy
                          ? 'Saving…'
                          : !widget.firstRun && step == 3
                              ? 'Review measurements'
                              : !widget.firstRun
                                  ? 'Save preferences'
                                  : step == 0
                                      ? 'Start'
                                      : step == 6
                                          ? 'Go to Home'
                                          : 'Continue')),
                  if (widget.firstRun && step == 0)
                    TextButton(
                        onPressed: busy ? null : () => save(skipAll: true),
                        child: const Text('Skip setup')),
                  if (widget.firstRun && step != 0 && step != 6)
                    TextButton(
                        onPressed: busy ? null : skip,
                        child: const Text('Skip for now')),
                  if (widget.firstRun && step > 0)
                    TextButton(
                        onPressed: busy
                            ? null
                            : () => setState(() => step = step == 2
                                ? 7
                                : step == 7
                                    ? 1
                                    : step - 1),
                        child: const Text('Back')),
                  if (result != null && !widget.firstRun) ...[
                    Text('Saved for ${result!.user.displayName}'),
                    for (final e in result!.user.priceRanges.entries)
                      if (e.value.length > 1)
                        Text(
                            '${e.key} · \$${e.value[0].toStringAsFixed(0)}–\$${e.value[1].toStringAsFixed(0)}')
                  ],
                ]));
}
