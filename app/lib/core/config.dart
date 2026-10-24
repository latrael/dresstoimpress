import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'settings.dart';

/// Loads/saves [Settings] in shared_preferences (edited on the Settings screen) and hands them to [Api].
///
/// The repo is public and the tunnel URL changes, so nothing secret is committed. Optional build-time
/// defaults: `flutter run --dart-define=DTI_API_BASE=https://... --dart-define=DTI_API_KEY=...`.
class Config {
  static const _baseKey = 'dti.apiBase';
  static const _apiKeyKey = 'dti.apiKey';
  static const _userKey = 'dti.userId';
  static const _heightKey = 'dti.heightCm';
  static const _weightKey = 'dti.weightKg';

  static const _defaultBase = String.fromEnvironment('DTI_API_BASE', defaultValue: 'http://127.0.0.1:8000');
  static const _defaultKey = String.fromEnvironment('DTI_API_KEY');

  static Settings get current => Api.instance.settings;

  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    String str(String key, String fallback) {
      final v = p.getString(key)?.trim() ?? '';
      return v.isEmpty ? fallback : v;
    }

    Api.instance.settings = Settings(
      baseUrl: str(_baseKey, _defaultBase),
      apiKey: str(_apiKeyKey, _defaultKey),
      userId: str(_userKey, 'u_demo'),
      heightCm: p.getDouble(_heightKey) ?? 170,
      weightKg: p.getDouble(_weightKey) ?? 65,
    );
  }

  static Future<void> save(Settings s) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_baseKey, s.baseUrl.trim());
    await p.setString(_apiKeyKey, s.apiKey.trim());
    await p.setString(_userKey, s.userId.trim());
    await p.setDouble(_heightKey, s.heightCm);
    await p.setDouble(_weightKey, s.weightKg);
    Api.instance.settings = s;
  }
}
