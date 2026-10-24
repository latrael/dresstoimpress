# App plan: FlutterFlow → plain Flutter

**Decided Fri Oct 23, ~9:10 PM.** FlutterFlow needs a paid plan for API calls, and exporting its code is paid too. So the app is rebuilt in **plain Flutter**: free, the same widgets Ryan already designed with, and it runs on any laptop.
- **Swift was considered and dropped:** it needs Xcode on every machine, and Ryan doesn't have it.
- **The backend doesn't change.** It's HTTPS + JSON with one header; routes are in `ADAM_TO_RYAN.md` and `NABIL_TO_RYAN.md`.
- **The design is still Ryan's Quick Browse spec** (`RYAN_TO_NABIL.md`). Rebuild his FlutterFlow screens from that spec and his fixtures; they're simple.

## Setup (15 min, any laptop)

1. **Install the Flutter SDK** (flutter.dev → Get started) and Chrome. Check with `flutter doctor`. Xcode and Android Studio are optional, and `flutter doctor` complaining about them is fine.
2. **Get the code:** branch `flutter-starter` (PR into `staging`), folder `app/`. Then `cd app && flutter pub get && flutter run -d chrome`.
3. **Backend:** in the app, open **Settings** and paste the tunnel URL and key (sent privately in the group chat). Tap "Test connection".
   - **Never put the URL or key in code or Git**; the repo is public. When Adam restarts the tunnel, paste the new URL in Settings.
4. **Phones:**
   - **Android:** plug in with USB debugging on, then `flutter run`.
   - **iPhone:** only on a Mac with Xcode (Adam's): `flutter run` with the phone plugged in, signed with a free Apple ID (Personal Team). Free certificates last 7 days.
5. **Demo user:** `u_demo`.
6. **Images on web:** product photos load through `GET /img?url=` on our backend, which needs no key. Retailer image servers don't always allow web apps to load their images directly.

## Layout (see `app/README.md` for the exact map)

```
app/lib/
  core/        config.dart (URL + key, saved on device) · api.dart (one method per route) · models.dart
  components/  shared widgets (price label, size chips, Fit Score badge, network image)
  features/
    feed/      Quick Browse + product page + try-on + complete the look
    cart/      cart, checkout, orders
    fitcheck/  posts, create, detail, tags, shop the fit
    closet/    grid, upload, duplicate prompt
    profile/   Style DNA, settings, onboarding
  (all of app/ → Ryan; core/ kept in sync by Adam)
```

**Rules:**
- **Ryan edits `app/`.** If a call or field is missing, ask Adam: he keeps `core/` in sync with the backend.
- **Branches:** `app/<you>-<thing>` → PR into `staging`. Before every PR: `flutter analyze` is clean, and it runs in Chrome against the live backend.
- **Never call `/swipe` for photo paging or vertical browsing** (Ryan's rule). Save = `PUT /wishlist/...`. Cart = `POST /cart/.../items`.
- **Packages:** only `http`, `shared_preferences` and `image_picker` unless the team agrees on more.

## Who builds what

**Ryan owns the whole app (`app/`).** Adam and Nabil stay on their backend tracks. That's fewer hand-offs, one consistent UI, and no merge fights.
- **The starter does the heavy lifting.** The `flutter-starter` PR wires all 5 tabs to the live backend with plain Material UI: Feed (Quick Browse), Cart/Checkout/Orders, Fit Check, Closet, Profile/Style DNA, plus the product page, try-on, complete-the-look and the Fit Score badge.
- **Ryan restyles and polishes it to his spec** instead of building from scratch.

### Ryan: the app, in this order
1. **Feed / Quick Browse + product page.** Match his wireframe: picture section, dots, info, description, size chips, Add to Cart, heart. No `/swipe` for paging or browsing.
2. **Cart → checkout `paid`** (the Saturday-noon checkpoint).
3. **Try it on + Complete the look** (the AI moments judges see).
4. **Fit Check:** feed, post, "Shop this fit".
5. **Closet, Profile / Style DNA, onboarding.**
6. Look and feel: theme, fonts, icon. Empty, loading and error states.

### Adam: AI backend (his track)
- AI routes and quality. He keeps `app/lib/core` (API + models) in sync whenever a backend route changes, and adds anything Ryan asks for.
- Hosts the backend (Mac + tunnel) and builds and runs the iPhone version for the demo.

### Nabil: commerce backend (his track)
- `/feed` should prefer ranked cards, so every card has a reason. Add fuller Fit Check seed tags (category, color, pattern, style_tags), and keep Nessie checkout solid.
- Owns the README for sponsor judges (Apify, Capital One / Nessie), the Devpost write-up and the demo script.

**Backup rule:** if the noon checkpoint is at risk, Adam or Nabil take one whole tab from Ryan's list, agreed in the group chat. Never a half-shared screen.

## Timeline

| When | Goal |
| --- | --- |
| **Fri night** | Starter merged to `staging`. Ryan runs it in Chrome against the live backend and starts the feed polish. |
| **Sat noon** | **End-to-end:** feed → size → add to cart → checkout `paid`, in Chrome and on a phone. |
| **Sat evening** | Try-on, complete the look, Fit Check post + shop the fit, Style DNA, Fit Score. Real fits photographed at the venue. |
| **Sat night** | Polish, empty/error states, demo script, Devpost write-up. |
| **Sun morning** | Feature freeze, record a backup demo video, submit. |

## Paste-in brief for your coding agent

> Repo `latrael/dresstoimpress`, branch from `staging`. The app is a plain Flutter project in `app/` (packages: http, shared_preferences, image_picker only). Read `docs/app-plan.md`, `app/README.md`, `ADAM_TO_RYAN.md`, `NABIL_TO_RYAN.md` and `RYAN_TO_NABIL.md` first. I own the whole app; work in the order in the plan. Use the API client in `core/`. If a backend call or field is missing, tell me so I can ask Adam, instead of guessing. Never call `/swipe` for photo paging or vertical browsing. Never put the backend URL or key in code. Load product images through the backend's `/img?url=` helper in `core/`. Run `flutter analyze` and test in Chrome (`flutter run -d chrome`) before each PR into `staging`.
