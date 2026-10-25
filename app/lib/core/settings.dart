/// Connection + demo-user settings the API reads on every call. Pure Dart (no Flutter),
/// so the API client and models also run under plain `dart run`.
class Settings {
  const Settings({
    this.baseUrl = 'http://127.0.0.1:8000',
    this.apiKey = '',
    this.userId = 'u_demo',
    this.heightCm = 170,
    this.weightKg = 65,
    this.sessionToken = '',
  });

  final String baseUrl;
  final String apiKey;
  final String userId;
  final double heightCm;
  final double weightKg;

  /// Our session token from POST /auth/google ('' = not signed in with Google: team / test accounts).
  final String sessionToken;

  /// Base URL without trailing slashes or whitespace.
  String get base {
    var b = baseUrl.trim();
    while (b.endsWith('/')) {
      b = b.substring(0, b.length - 1);
    }
    return b;
  }

  Settings copyWith({String? baseUrl, String? apiKey, String? userId, double? heightCm, double? weightKg,
          String? sessionToken}) =>
      Settings(
        baseUrl: baseUrl ?? this.baseUrl,
        apiKey: apiKey ?? this.apiKey,
        userId: userId ?? this.userId,
        heightCm: heightCm ?? this.heightCm,
        weightKg: weightKg ?? this.weightKg,
        sessionToken: sessionToken ?? this.sessionToken,
      );
}
