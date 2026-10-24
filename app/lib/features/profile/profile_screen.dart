import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';
import '../product/try_on.dart';
import '../closet/closet_screen.dart';
import 'onboarding_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, required this.api, required this.onChanged});
  final Api api;
  final Future<void> Function() onChanged;
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool busy = false;
  int revision = 0;
  String? message;
  StyleProfile? applied;
  Future<({AppUser user, StyleProfile style})> load() async {
    final user = await widget.api.getUser();
    final style = await widget.api.style();
    return (user: user, style: style);
  }

  Future<void> apply() async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      final result = await widget.api.applyStyle();
      if (!mounted) return;
      setState(() {
        applied = result.profile;
        message = 'Your learned budgets are saved.';
      });
      await widget.onChanged();
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => message = e.status == 409
            ? 'Save at least five pieces to learn your style before applying budgets.'
            : 'Could not apply your style. Try again.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => message = 'Could not apply your style. Try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> preferences() async {
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) =>
                OnboardingScreen(api: widget.api, onSaved: widget.onChanged)));
    if (mounted) {
      setState(() {
        revision++;
        applied = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Your profile',
      actions: [
        IconButton(
            tooltip: 'Style and budget',
            onPressed: preferences,
            icon: const Icon(Icons.tune))
      ],
      child: AsyncContent<({AppUser user, StyleProfile style})>(
          key: ValueKey(revision),
          load: load,
          builder: (data) {
            final style = applied ?? data.style;
            return ListView(padding: const EdgeInsets.all(24), children: [
              Text(data.user.displayName,
                  style: Theme.of(context).textTheme.headlineMedium),
              if (data.user.styleText.isNotEmpty) Text(data.user.styleText),
              const SizedBox(height: 12),
              Wrap(spacing: 8, children: [
                OutlinedButton.icon(
                    onPressed: preferences,
                    icon: const Icon(Icons.tune),
                    label: const Text('Style and budget')),
                OutlinedButton.icon(
                    onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => ClosetScreen(api: widget.api))),
                    icon: const Icon(Icons.checkroom),
                    label: const Text('Your closet')),
              ]),
              const SizedBox(height: 20),
              Text('Your Style DNA',
                  style: Theme.of(context).textTheme.headlineSmall),
              Text(style.headline.isEmpty
                  ? 'Save pieces to help us learn your style.'
                  : style.headline),
              Text(
                  '${style.confidence} confidence · ${style.sampleSize['liked'] ?? 0} liked pieces'),
              const SizedBox(height: 12),
              Wrap(spacing: 8, children: [
                for (final tag in style.styles)
                  Chip(
                      label: Text('${tag.tag} · ${(tag.share * 100).round()}%'))
              ]),
              if (style.palette.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Your palette',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                Wrap(spacing: 10, runSpacing: 8, children: [
                  for (final color in style.palette)
                    Chip(
                        avatar: CircleAvatar(
                            backgroundColor: parseColor(color.hex)),
                        label: Text(
                            '${color.name} · ${(color.share * 100).round()}%'))
                ]),
              ],
              if (style.patterns.isNotEmpty)
                Text(
                    'Patterns · ${style.patterns.entries.map((e) => '${e.key} ${(e.value * 100).round()}%').join(', ')}'),
              Text('Formality · ${style.formalityLabel}'),
              if (style.favoriteRetailers.isNotEmpty)
                Text(
                    'Favorite stores · ${style.favoriteRetailers.map((r) => r.retailer).join(', ')}'),
              if (style.avoid.isNotEmpty)
                Text('Usually skip · ${style.avoid.join(', ')}'),
              const SizedBox(height: 16),
              const Text('Learned budgets',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              for (final e in style.priceRanges.entries)
                if (e.value.length >= 2)
                  Text(
                      '${e.key} · \$${e.value[0].toStringAsFixed(0)}–\$${e.value[1].toStringAsFixed(0)}'),
              FilledButton.tonal(
                  onPressed: busy ? null : apply,
                  child: Text(busy ? 'Saving…' : 'Use learned budgets')),
              if (message != null) Text(message!),
              const SizedBox(height: 24),
              Text('Personal try-on',
                  style: Theme.of(context).textTheme.titleLarge),
              BodyPhotoButton(api: widget.api),
            ]);
          }));
}

Color parseColor(String hex) {
  final value = hex.replaceFirst('#', '');
  final parsed = value.length == 6 ? int.tryParse(value, radix: 16) : null;
  return parsed == null ? Colors.grey : Color(0xff000000 | parsed);
}
