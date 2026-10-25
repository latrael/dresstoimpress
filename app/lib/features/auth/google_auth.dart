import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// Google Sign-In for `POST /auth/google` (docs/auth-google.md). OAuth client ids are public (they ship inside
/// every app), so the team's are the defaults here; a build can override them with
/// `--dart-define=GOOGLE_SERVER_CLIENT_ID=...` / `--dart-define=GOOGLE_IOS_CLIENT_ID=...` (Nabil's local
/// bundle id `com.nabil.dressToImpress` has its own iOS client). Android needs no id here: Google matches the
/// app by package name + signing SHA-1 and the token's audience is the web (server) client.
class GoogleAuth {
  static const serverClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID',
      defaultValue: '43902770892-itpsnesq1jfvskr8jn1l25hli51m92v6.apps.googleusercontent.com');
  // iOS client for the team bundle id com.dresstoimpress.dressToImpress
  static const iosClientId = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID',
      defaultValue: '43902770892-2u86506g9nhtdsliu673of6n6hosq51a.apps.googleusercontent.com');

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
