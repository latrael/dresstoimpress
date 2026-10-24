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
    feed/      Quick Browse + product page + try-on      → Ryan
    cart/      cart, checkout, orders                    → Nabil
    fitcheck/  posts, create, detail, tags, shop the fit → Nabil
    closet/    grid, upload, duplicate prompt            → Adam
    profile/   Style DNA, settings, onboarding           → Adam (onboarding: Ryan)
```

**Rules, so nobody's work crosses:**
- **Only edit files in your own `features/` folder.** Need a new API method or model field? Add it in `core/` in a small PR and tag Adam, or ask him. He keeps `core/` in sync with the backend.
- **Branches:** `app/<you>-<thing>` → PR into `staging`. Before every PR: `flutter analyze` is clean, and it runs in Chrome against the live backend.
- **Never call `/swipe` for photo paging or vertical browsing** (Ryan's rule). Save = `PUT /wishlist/...`. Cart = `POST /cart/.../items`.
- **Packages:** only `http`, `shared_preferences` and `image_picker` unless the team agrees on more.

## Who builds what, in order

### Ryan: Feed tab (the demo's core)
1. **Quick Browse:**
   - Vertical `PageView` over `GET /feed?user_id=u_demo&limit=20`.
   - Each page: picture section (horizontal `PageView` over `images[]`, starting only inside the picture; dots hidden for 1 image), brand + name + price (sale price with the original struck through), AI `reason` (hide when empty), description (hide when null).
   - Size chips from `sizes` (grey out `in_stock: false`; pre-select from `POST /size`) and **Add to Cart** (`POST /cart/{user}/items {product_id, size, qty: 1}`; show the 422 `detail`).
   - Heart: `PUT` / `DELETE /wishlist/{user}/items/{id}`, initialised from `GET /wishlist/{user}/ids`.
2. **Try it on:** a button → `POST /tryon {user_id, product_ids: [id]}`. ~5 s, so show a loader. When `mode == "collage"`, label the result "Outfit board".
3. **Complete the look:** a button → `POST /complete-look {user_id, product_id}`. A sheet lists the items (closet pieces marked "yours"), shows `new_items_total_usd`, and offers "Add all". Put the Fit Score badge on it: `POST /ai/fit-score {product_ids, closet_item_ids}`.
4. **Onboarding:** height/weight (for `/size`) and the full-body photo (`POST /users/{id}/body-photo`, multipart `file`).
5. Look and feel: theme, fonts, icon.

### Nabil: Cart + Fit Check tabs (his routes)
1. **Cart:** `GET /cart/{user}`, grouped by store with subtotals and a total; remove with `DELETE /cart/{user}/items/{id}?size=`.
2. **Checkout:** `POST /checkout/{user}`, then a receipt showing each purchase's `status`: `paid`, or `nessie_failed` with a retry. On **409**, `detail` is an object: show `detail.message` and keep the cart. Then `GET /orders/{user}`.
3. **Fit Check feed:** `GET /fitcheck/feed?user_id=` → photo, caption, author, like (`POST .../like`), comment count.
4. **Create a post:** image_picker → multipart `POST /fitcheck` (`user_id`, `file`, `caption`). The AI pre-fills tags; the owner edits them with `PATCH /fitcheck/{id}/tags`.
5. **Post detail:** tags, comments, the **Fit Score badge** (`POST /ai/fit-score {items: post.tagged}`), and **"Shop this fit"** (`GET /fitcheck/{id}/shop?user_id=`): cards with `reason` and Add to Cart.

### Adam: core + Closet + Profile + shared AI pieces
1. Keep `core/api.dart` and `models.dart` in sync with the backend, and review `core/` PRs.
2. **Closet:** `GET /closet/{user}` grid; upload via image_picker → `POST /closet/upload`. If `duplicate_of` is set: "Looks like you already have this" → **Keep both** / **Remove** (`DELETE /closet/{user}/{id}`).
3. **Profile:** the Style DNA card (`GET /users/{id}/style`: headline, style shares, palette swatches from `hex`, formality, price ranges) with a "Use these budgets" button (`POST /users/{id}/style/apply`), plus Settings.
4. **Fit Score badge** widget (`score` + `verdict`; tap shows `notes`), used by Ryan and Nabil.
5. Builds and runs the iPhone version on his Mac for the demo.

## Timeline

| When | Goal |
| --- | --- |
| **Fri night** | Starter merged to `staging`. Everyone runs it in Chrome against the live backend and starts their tab 1 task. |
| **Sat noon** | **End-to-end:** feed → size → add to cart → checkout `paid`, in Chrome and on a phone (Ryan + Nabil). Closet upload works (Adam). |
| **Sat evening** | Try-on, complete the look, Fit Check post + shop the fit, Style DNA, Fit Score. Real fits photographed at the venue. |
| **Sat night** | Polish, empty/error states, demo script, Devpost write-up. |
| **Sun morning** | Feature freeze, record a backup demo video, submit. |

## Paste-in brief for your coding agent

> Repo `latrael/dresstoimpress`, branch from `staging`. The app is a plain Flutter project in `app/` (packages: http, shared_preferences, image_picker only). Read `docs/app-plan.md`, `app/README.md`, `ADAM_TO_RYAN.md`, `NABIL_TO_RYAN.md` and `RYAN_TO_NABIL.md` first. My part: **<your section above>**. Only edit `app/lib/features/<my folder>/` (and `components/` for shared widgets I own). Use the API client in `core/`. If a call or field is missing, tell me instead of editing `core/`. Never call `/swipe` for photo paging or vertical browsing. Never put the backend URL or key in code. Load product images through the backend's `/img?url=` helper in `core/`. Run `flutter analyze` and test in Chrome (`flutter run -d chrome`) before each PR into `staging`.
