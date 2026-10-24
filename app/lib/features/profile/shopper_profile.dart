import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Explicit user measurements only; never substitute the connection defaults.
class ShopperProfile {
  const ShopperProfile(
      {this.completed = false,
      this.style = '',
      this.fit = 'regular',
      this.usualSize = '',
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

  Future<void> save(String user) async {
    final p = await SharedPreferences.getInstance();
    final ok = await p.setString(
        key(user),
        jsonEncode({
          'completed': completed,
          'style': style,
          'fit': fit,
          'usualSize': usualSize,
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
