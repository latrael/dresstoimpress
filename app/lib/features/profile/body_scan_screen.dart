import 'package:flutter/material.dart';
import '../../core/api.dart';
import 'measurement_picker.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';

/// Body scan: height (and optional weight) + a full-body photo -> AI-estimated measurements, saved to
/// the user's server profile (used by sizing) and the photo becomes the try-on photo. Pops with the
/// [BodyProfile] so onboarding can pre-fill its measurement fields.
class BodyScanScreen extends StatefulWidget {
  const BodyScanScreen(
      {super.key,
      required this.api,
      this.picker = pickPhoto,
      this.heightCm,
      this.weightKg});
  final Api api;
  final PhotoPicker picker;
  final double? heightCm, weightKg;
  @override
  State<BodyScanScreen> createState() => _BodyScanScreenState();
}

class _BodyScanScreenState extends State<BodyScanScreen> {
  late final height = TextEditingController(text: _text(widget.heightCm));
  late final weight = TextEditingController(text: _text(widget.weightKg));
  bool busy = false;
  String? error;
  BodyProfile? result;

  static String _text(double? v) =>
      v == null || v <= 0 ? '' : v.toStringAsFixed(v % 1 == 0 ? 0 : 1);

  @override
  void dispose() {
    height.dispose();
    weight.dispose();
    super.dispose();
  }

  Future<void> scan() async {
    final h = double.tryParse(height.text.trim());
    final w =
        weight.text.trim().isEmpty ? null : double.tryParse(weight.text.trim());
    if (h == null || h < 120 || h > 230) {
      setState(() => error = 'Choose your height first.');
      return;
    }
    if (weight.text.trim().isNotEmpty && (w == null || w < 30 || w > 250)) {
      setState(
          () => error = 'Choose a weight from 66–550 lb, or leave it blank.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final photo = await widget.picker();
      if (photo == null) return;
      final scanned = await widget.api.bodyScan(photo.bytes,
          heightCm: h, weightKg: w, mimeType: photo.mimeType);
      if (mounted) setState(() => result = scanned.profile);
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => error = e.status == 422
            ? 'Check your height and weight, then try again.'
            : 'Could not scan this photo. Try again.');
      }
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = result;
    return FeaturePage(
        title: 'Body scan',
        child: ListView(padding: const EdgeInsets.all(24), children: [
          const Text(
              'Enter your height, then choose a full-body photo: standing, head to feet, fitted clothes if you can. We estimate your measurements from it. They are a starting point: check them and edit any that look off.'),
          const SizedBox(height: 16),
          MeasurementPicker(
              kind: 'Height (cm)',
              value: double.tryParse(height.text),
              enabled: !busy,
              onChanged: (v) =>
                  setState(() => height.text = v?.toString() ?? '')),
          MeasurementPicker(
              kind: 'Weight (kg)',
              value: double.tryParse(weight.text),
              enabled: !busy,
              onChanged: (v) =>
                  setState(() => weight.text = v?.toString() ?? '')),
          const SizedBox(height: 16),
          FilledButton.icon(
              onPressed: busy ? null : scan,
              icon: const Icon(Icons.accessibility_new),
              label: Text(busy
                  ? 'Scanning…'
                  : r == null
                      ? 'Choose full-body photo'
                      : 'Scan another photo')),
          const SizedBox(height: 8),
          const Text(
              'The photo is uploaded to your connected Niche server and also used for your personal try-on.'),
          if (error != null)
            Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error))),
          if (r != null) ...[
            const SizedBox(height: 24),
            Text('Your estimates',
                style: Theme.of(context).textTheme.titleLarge),
            if (r.fullBody == false)
              const Text(
                  'This photo did not show your full body, so these come from your height and weight only.'),
            for (final line in bodyProfileLines(r)) Text(line),
            if (r.note.isNotEmpty)
              Padding(
                  padding: const EdgeInsets.only(top: 8), child: Text(r.note)),
            const SizedBox(height: 16),
            FilledButton(
                onPressed: () => Navigator.pop(context, r),
                child: const Text('Use these measurements')),
          ],
        ]));
  }
}

/// Human-readable measurement lines for a body profile (the server stores inches).
List<String> bodyProfileLines(BodyProfile p) {
  String inch(double? v) => v == null ? '' : '${v.toStringAsFixed(1)} in';
  return [
    if (p.heightCm > 0)
      'Height · ${(p.heightCm / 2.54).round() ~/ 12} ft ${(p.heightCm / 2.54).round() % 12} in',
    if (p.weightKg != null)
      'Weight · ${(p.weightKg! / .45359237).toStringAsFixed(0)} lb',
    if (p.chestIn != null) 'Chest · ${inch(p.chestIn)}',
    if (p.waistIn != null) 'Waist · ${inch(p.waistIn)}',
    if (p.hipIn != null) 'Hips · ${inch(p.hipIn)}',
    if (p.inseamIn != null) 'Inseam · ${inch(p.inseamIn)}',
    if (p.shoeUs != null) 'Shoe · US ${p.shoeUs}',
    if (p.build != null) 'Build · ${p.build}',
    'Source · ${p.source == 'ai' ? 'body scan' : p.source == 'manual' ? 'entered by you' : 'estimated from height and weight'}',
  ];
}
