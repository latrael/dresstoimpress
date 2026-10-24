import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api.dart';
import '../../core/models.dart';

/// Explicit user measurements only; never substitute the connection defaults.
class ShopperProfile {
  const ShopperProfile(
      {this.completed = false,
      this.style = '',
      this.fit = 'regular',
      this.usualSize = '',
      this.usualSizes = const {},
      this.preferredStores = const [],
      this.otherStores = '',
      this.heightCm,
      this.weightKg,
      this.waistCm,
      this.chestCm,
      this.hipCm,
      this.inseamCm,
      this.shoeUs,
      this.budgets = const {}});
  final bool completed;
  final String style, fit, usualSize;
  final Map<String, String> usualSizes;
  final List<String> preferredStores;
  final String otherStores;
  final double? heightCm, weightKg, waistCm, chestCm, hipCm, inseamCm, shoeUs;
  final Map<String, double> budgets;
  static String key(String user) => 'niche.shopper.v1.$user';
  static Future<ShopperProfile> load(String user) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key(user));
    if (raw == null) return const ShopperProfile();
    try {
      final j = jsonDecode(raw) as Map<String, dynamic>;
      double? n(String k) => (j[k] as num?)?.toDouble();
      return ShopperProfile(
          completed: j['completed'] == true,
          style: j['style'] as String? ?? '',
          fit: j['fit'] as String? ?? 'regular',
          usualSize: j['usualSize'] as String? ?? '',
          usualSizes: Map<String, String>.from(j['usualSizes'] as Map? ?? {}),
          preferredStores:
              List<String>.from(j['preferredStores'] as List? ?? []),
          otherStores: j['otherStores'] as String? ?? '',
          heightCm: n('heightCm'),
          weightKg: n('weightKg'),
          waistCm: n('waistCm'),
          chestCm: n('chestCm'),
          hipCm: n('hipCm'),
          inseamCm: n('inseamCm'),
          shoeUs: n('shoeUs'),
          budgets: (j['budgets'] as Map? ?? {})
              .map((k, v) => MapEntry(k as String, (v as num).toDouble())));
    } catch (_) {
      return const ShopperProfile();
    }
  }

  /// A copy with the measurements from a body scan or the server profile (inches -> cm). Fields the
  /// body profile doesn't have keep their current value. [gapsOnly]: only fill fields that are blank
  /// here (restoring from the server); otherwise the body profile wins (a fresh scan).
  ShopperProfile withBody(BodyProfile b, {bool gapsOnly = false}) {
    double? cm(double? inches) => inches == null
        ? null
        : double.parse((inches * 2.54).toStringAsFixed(1));
    double? pick(double? mine, double? theirs) =>
        gapsOnly ? mine ?? theirs : theirs ?? mine;
    return ShopperProfile(
        completed: completed,
        style: style,
        fit: gapsOnly ? fit : b.fit ?? fit,
        usualSize: usualSize,
        usualSizes: {...usualSizes, ...b.usualSizes},
        preferredStores: preferredStores,
        otherStores: otherStores,
        heightCm: pick(heightCm, b.heightCm > 0 ? b.heightCm : null),
        weightKg: pick(weightKg, b.weightKg),
        waistCm: pick(waistCm, cm(b.waistIn)),
        chestCm: pick(chestCm, cm(b.chestIn)),
        hipCm: pick(hipCm, cm(b.hipIn)),
        inseamCm: pick(inseamCm, cm(b.inseamIn)),
        shoeUs: pick(shoeUs, b.shoeUs),
        budgets: budgets);
  }

  /// Saves the measurements to the user's server profile too (D5: onboarding answers live on the
  /// server, so sizing and AI use them on any device). Blank fields clear the server value.
  Future<void> syncToServer(Api api) => api.updateBodyProfile(
      heightCm: heightCm,
      weightKg: weightKg,
      waistCm: waistCm,
      chestCm: chestCm,
      hipCm: hipCm,
      inseamCm: inseamCm,
      shoeUs: shoeUs,
      fit: fit,
      usualSizes: usualSizes.isNotEmpty
          ? usualSizes
          : usualSize.isEmpty
              ? null
              : {'top': usualSize, 'outerwear': usualSize, 'dress': usualSize});

  ShopperProfile withCompletion(bool value) => ShopperProfile(
      completed: value,
      style: style,
      fit: fit,
      usualSize: usualSize,
      usualSizes: usualSizes,
      preferredStores: preferredStores,
      otherStores: otherStores,
      heightCm: heightCm,
      weightKg: weightKg,
      waistCm: waistCm,
      chestCm: chestCm,
      hipCm: hipCm,
      inseamCm: inseamCm,
      shoeUs: shoeUs,
      budgets: budgets);

  Future<void> save(String user) async {
    final p = await SharedPreferences.getInstance();
    final ok = await p.setString(
        key(user),
        jsonEncode({
          'completed': completed,
          'style': style,
          'fit': fit,
          'usualSize': usualSize,
          'usualSizes': usualSizes,
          'preferredStores': preferredStores,
          'otherStores': otherStores,
          'heightCm': heightCm,
          'weightKg': weightKg,
          'waistCm': waistCm,
          'chestCm': chestCm,
          'hipCm': hipCm,
          'inseamCm': inseamCm,
          'shoeUs': shoeUs,
          'budgets': budgets
        }));
    if (!ok) throw StateError('Preferences could not be saved');
  }
}
