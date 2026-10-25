# Google sign-in

Status (Sun Oct 25, ~7:15 AM): backend (#90) and app (#93) merged; OAuth clients created (Google Cloud project
"Niche", External / Testing: only listed **test users** can sign in). Login is **optional** until `AUTH_REQUIRED=1`.

OAuth clients (public ids; never commit the web client's *secret*, which we don't use):

| Client | Id | Used by |
| --- | --- | --- |
| Web ("Niche server") | `43902770892-itpsnesq1jfvskr8jn1l25hli51m92v6…` | `serverClientId` in the app = the ID token's audience the server checks |
| iOS team | `43902770892-2u86506g9nhtdsliu673of6n6hosq51a…` | bundle `com.dresstoimpress.dressToImpress` (default in `GoogleAuth`) |
| iOS Nabil | `43902770892-ppf9mblaraum6tgui4hpn8usf43pffkn…` | bundle `com.nabil.dressToImpress` (`--dart-define=GOOGLE_IOS_CLIENT_ID=…`) |
| Android (Adam, debug) | `43902770892-u37ldkujvcnvkc8rjfe1mgfev90k2vqa…` | package `com.dresstoimpress.dress_to_impress`, SHA-1 `46:A8:5D:…:C1:85`. Not needed in the app or on the server: Android tokens are issued for the web client |

Server: `GOOGLE_CLIENT_IDS` = the web + both iOS ids, comma-separated (full ids in `NABIL_TO_ADAM.md`, 7:15 AM).

## How it works

1. The app signs the user in with `google_sign_in` and gets a Google **ID token**.
2. The app sends it to `POST /auth/google`. The server checks it and returns **our own session token**.
3. The app stores that token and sends `Authorization: Bearer <token>` on every call, next to `X-DTI-Key`.

The `X-DTI-Key` tunnel key is unchanged and still required on `/auth/*`.

## Contract

### `POST /auth/google`

```json
{ "id_token": "<Google ID token>", "link_user_id": "u_adam" }
```

`link_user_id` is optional. Use it once, to attach a Google account to an existing user (a team
account or an already onboarded user) that has no Google account yet.

Response `200`:

```json
{ "token": "<session token>", "user": { "id": "u_ada-lovelace-3f2a", "display_name": "Ada Lovelace", "auth": [{"provider": "google", "sub": "1043...", "email": "ada@gmail.com"}], "...": "the usual User fields" }, "created": true }
```

- `created: true` means a new user was made. Send them through onboarding.
- The user is matched by Google's `sub` (stable account id), never by email.
- A new user gets an id like `u_<name-slug>-xxxx` and `display_name` from the Google name.

Errors:

| Code | When |
| --- | --- |
| 401 | Bad or expired ID token, wrong audience or issuer, or email not verified |
| 404 | `link_user_id` doesn't exist |
| 409 | `link_user_id` already has a Google account, or this Google account belongs to another user |
| 503 | The server has no `GOOGLE_CLIENT_IDS` set |

The server checks: RS256 signature against Google's public keys (cached), `exp`/`iat`, `aud` is one of
`GOOGLE_CLIENT_IDS`, `iss` is `accounts.google.com` or `https://accounts.google.com`, `email_verified`.

### `GET /auth/me`

`Authorization: Bearer <token>`. Returns the `User`, or `401` if the token is missing, wrong, expired or
revoked. Use it on app start to check a saved token.

### `POST /auth/logout`

`Authorization: Bearer <token>`. Returns `{"revoked": true}` and the token stops working.

### Every other route

| Request | Result |
| --- | --- |
| No `Authorization` header | Same as today: the server trusts the `user_id` the app sends |
| Valid `Bearer` token, `user_id` (path, query, JSON body or form field) is the token's user, or absent | Works |
| Valid token, `user_id` is someone else | `403 user_id does not match the signed-in user` |
| Token sent but invalid / expired / malformed | `401 invalid or expired session` (sign in again) |
| `AUTH_REQUIRED=1` and no token, on a route that takes a `user_id` | `401 sign in required` |

Keep sending `user_id` as today. With a token it must match the signed-in user.

Always open (no token needed): `/health`, `/static/*`, `/img`, `/fit`, `/fit/*`, `/auth/google`.

Sessions last **30 days**. Only a SHA-256 hash of the token is stored (collection `sessions`).

## Server env vars (Nabil)

| Var | Value |
| --- | --- |
| `GOOGLE_CLIENT_IDS` | Comma-separated OAuth client ids allowed as `aud`: web, iOS, Android. Example: `123-web.apps.googleusercontent.com,123-ios.apps.googleusercontent.com,123-android.apps.googleusercontent.com` |
| `AUTH_REQUIRED` | `1` = strict mode (routes with a `user_id` need a token). Unset or `0` = optional (default) |

No new install: `google-auth` was already in the venv (it comes with `google-genai`). It is now listed
in `requirements.txt` because `app/auth.py` imports it directly.

## Google Cloud Console (Nabil)

1. Pick or create a Google Cloud project.
2. **OAuth consent screen**: User type External, app name "Dress to Impress", support email, scopes
   `openid`, `email`, `profile`. Leave it in **Testing** and add every tester's Gmail under Test users
   (up to 100). Testing mode needs no Google review.
3. **Credentials > Create credentials > OAuth client ID**, three times:
   - **Web application**: Authorized JavaScript origins = where the Flutter web build is served
     (for example `http://localhost:5000` and the deployed web URL). This id is also the
     `serverClientId` for iOS and Android.
   - **iOS**: bundle id `com.dresstoimpress.dressToImpress`.
   - **Android**: package `com.dresstoimpress.dress_to_impress` + the SHA-1 of every signing key used.
     Each teammate's debug key is different. Get it with
     `keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android`.
     Add one Android client per SHA-1, or add the fingerprints to the same client.
4. Put all the client ids in `GOOGLE_CLIENT_IDS` in the server `.env` and restart.
5. Send Ryan/Adam the web client id, the iOS client id and its reversed form (shown on the iOS client
   page as "iOS URL scheme").

## App (Ryan / Adam)

1. `flutter pub add google_sign_in` (v7).
2. Initialise once at startup:
   ```dart
   await GoogleSignIn.instance.initialize(
     clientId: Platform.isIOS ? '<IOS_CLIENT_ID>' : null,
     serverClientId: '<WEB_CLIENT_ID>', // iOS + Android: the ID token's aud becomes the web client id
   );
   ```
   On web, pass `clientId: '<WEB_CLIENT_ID>'` and no `serverClientId`.
3. **iOS** `ios/Runner/Info.plist`:
   ```xml
   <key>GIDClientID</key><string>IOS_CLIENT_ID</string>
   <key>GIDServerClientID</key><string>WEB_CLIENT_ID</string>
   <key>CFBundleURLTypes</key>
   <array><dict>
     <key>CFBundleURLSchemes</key>
     <array><string>com.googleusercontent.apps.REVERSED_IOS_ID</string></array>
   </dict></array>
   ```
   The URL scheme is the iOS client id reversed (Console shows it). Rebuild and re-sign after.
4. **Android**: nothing in the manifest. It needs the Android OAuth client (package + SHA-1) to exist,
   and `serverClientId` set as above, or no ID token comes back.
5. **Web**: `authenticate()` isn't supported on web in v7. Render Google's button
   (`google_sign_in_web`'s `renderButton()`) and listen to `GoogleSignIn.instance.authenticationEvents`.
6. Sign in and send the ID token:
   ```dart
   final account = await GoogleSignIn.instance.authenticate();
   final idToken = account.authentication.idToken;
   final res = await api.post('/auth/google', {'id_token': idToken /*, 'link_user_id': currentTeamUserId */});
   // res: {token, user, created}
   ```
   Send `link_user_id` only when a team / onboarded user signs in with Google for the first time.
7. Save `token` (`shared_preferences`, or `flutter_secure_storage` if we add it) and `user.id`
   (that becomes `_user`).
8. In `Api._send` / `_upload` / `_uploadMany`, add `Authorization: Bearer <token>` when a token is
   saved, next to `X-DTI-Key`. Keep sending `user_id` as today.
9. On app start with a saved token, call `GET /auth/me`. A `401` (or `401` on any call) means: clear
   the token and show sign-in.
10. Sign out: `POST /auth/logout`, clear the token, and `GoogleSignIn.instance.signOut()`.
11. `created: true` means a new user: send them to onboarding.
