import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// Google Sign-In for `POST /auth/google` (docs/auth-google.md). The OAuth client ids are build-time defines,
/// like the tunnel URL: `--dart-define=GOOGLE_SERVER_CLIENT_ID=<web client id>` (the ID token's audience,
/// which the server checks) and, on iOS, `--dart-define=GOOGLE_IOS_CLIENT_ID=<iOS client id for this bundle id>`.
/// Without them the Google button stays hidden and the team / test accounts work as before.
class GoogleAuth {
  static const serverClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');
  static const iosClientId = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');

  /// Phones only for now: the web build needs Google's own rendered button (a later step).
  static bool get available =>
      serverClientId.isNotEmpty &&
      !kIsWeb &&
      (defaultTargetPlatform != TargetPlatform.iOS || iosClientId.isNotEmpty);

  static Future<void>? _init;

  static Future<void> _ready() => _init ??= GoogleSignIn.instance.initialize(
      clientId: iosClientId.isEmpty ? null : iosClientId, serverClientId: serverClientId);

  /// Shows Google's account picker and returns the ID token for our server. Null if the user cancelled.
  static Future<String?> idToken() async {
    await _ready();
    try {
      final account = await GoogleSignIn.instance.authenticate();
      final token = account.authentication.idToken;
      if (token == null || token.isEmpty) throw StateError('Google returned no ID token');
      return token;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) return null;
      rethrow;
    }
  }

  /// Forget the Google account on this device (our own session is revoked separately via POST /auth/logout).
  static Future<void> signOut() async {
    if (!available) return;
    try {
      await _ready();
      await GoogleSignIn.instance.signOut();
    } catch (_) {/* best effort: the server session is what matters */}
  }
}
