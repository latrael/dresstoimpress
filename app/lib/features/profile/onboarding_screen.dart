import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, required this.api, required this.onSaved});
  final Api api;
  final Future<void> Function() onSaved;
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final name = TextEditingController();
  final text = TextEditingController();
  OnboardingResult? result;
  String? error;
  bool busy = false;
  @override
  void dispose() {
    name.dispose();
    text.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (text.text.trim().isEmpty) {
      setState(() => error = 'Tell us a little about your style and budget.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
      result = null;
    });
    try {
      final saved = await widget.api.onboarding(text.text.trim(),
          displayName: name.text.trim().isEmpty ? null : name.text.trim());
      if (!mounted) return;
      setState(() => result = saved);
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
      title: 'Your style',
      child: ListView(padding: const EdgeInsets.all(24), children: [
        Text('Make it feel like you',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        const Text(
            r'Describe what you like and what you want to spend. For example: Y2K, tops under $40, jeans $30–$70.'),
        const SizedBox(height: 20),
        TextField(
            controller: name,
            enabled: !busy,
            decoration:
                const InputDecoration(labelText: 'Display name (optional)')),
        const SizedBox(height: 16),
        TextField(
            controller: text,
            enabled: !busy,
            minLines: 3,
            maxLines: 6,
            decoration: const InputDecoration(labelText: 'Style and budget')),
        const SizedBox(height: 20),
        FilledButton(
            onPressed: busy ? null : save,
            child: Text(busy ? 'Saving…' : 'Save preferences')),
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
