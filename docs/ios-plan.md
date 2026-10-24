# iOS plan: FlutterFlow → SwiftUI

**Decided Fri Oct 23, ~9 PM.** FlutterFlow needs a paid plan for API calls, so the app is now a native SwiftUI app.
- **The backend doesn't change.** It's plain HTTPS + JSON with one header, and every route in `ADAM_TO_RYAN.md` / `NABIL_TO_RYAN.md` stays the same.
- **Ryan's Quick Browse spec** (`RYAN_TO_NABIL.md`) is still the design.

## Setup (10 min)

1. **A Mac with Xcode 16+.** Adam's Mac has it; anyone without a Mac pairs on his.
2. **Branches:** the starter app is on `ios-starter` (PR into `staging`), under `ios/`. Open `ios/DressToImpress.xcodeproj`.
3. **Signing:** Signing & Capabilities → Team → your **Personal Team**, using a free Apple ID. No paid developer account is needed.
   - Run on the simulator, or on your iPhone over USB. On the phone, trust the developer in Settings → General → VPN & Device Management. Free certificates last 7 days.
4. **Backend:** open the app's **Settings** screen and paste the tunnel URL and key (sent privately in the group chat). Tap "Test connection".
   - **Never put the URL or key in code or Git**; the repo is public. The URL changes when Adam restarts the tunnel. Just paste the new one in Settings.
5. **Demo user:** `u_demo`.

## Layout (see `ios/README.md` for the exact map)

```
ios/DressToImpress/
  Core/        Config.swift (URL + key in UserDefaults) · API.swift (one async method per route) · Models.swift (Codable)
  Components/  shared views (price label, size chips, Fit Score badge, async image)
  Features/
    Feed/      Quick Browse + product page + try-on      → Ryan
    Cart/      cart, checkout, orders                    → Nabil
    FitCheck/  posts, create, detail, tags, shop the fit → Nabil
    Closet/    grid, upload, duplicate prompt            → Adam
    Profile/   Style DNA, settings, onboarding photo     → Adam (onboarding: Ryan)
```

**Rules, so nobody's work crosses:**
- **Only edit files in your own `Features/` folder.** Need a new API method or model field? Add it in `Core/` in a small PR and tag Adam, or ask him. He keeps `Core/` in sync with the backend schema.
- **Branches:** `ios/<you>-<thing>` → PR into `staging`. Before every PR: build passes, and it runs on the simulator against the live backend.
- **Never call `/swipe` for photo paging or vertical browsing** (Ryan's rule). Save = `PUT /wishlist/...`. Cart = `POST /cart/.../items`.
- **No third-party packages.** Use SwiftUI, URLSession, AsyncImage and PhotosPicker.

## Who builds what, in order

### Ryan: Feed tab (the demo's core)
1. **Quick Browse:**
   - Vertical paging over `GET /feed?user_id=u_demo&limit=20`.
   - Each page: picture section (horizontal paging over `images[]`, dots hidden for 1 image), brand + name + price (sale price with the original struck through), AI `reason` (hide when empty), description (hide when null).
   - Size chips from `sizes` (grey out `in_stock: false`; pre-select from `POST /size`) and **Add to Cart** (`POST /cart/{user}/items {product_id, size, qty: 1}`; show the 422 `detail`).
   - Heart: `PUT` / `DELETE /wishlist/{user}/items/{id}`, initialised from `GET /wishlist/{user}/ids`.
2. **Try it on:** a button on the product page → `POST /tryon {user_id, product_ids: [id]}`. ~5 s, so show a loader. When `mode == "collage"`, label the result "Outfit board".
3. **Complete the look:** a button → `POST /complete-look {user_id, product_id}`. A sheet lists the items (closet pieces marked "yours"), shows `new_items_total_usd`, and offers "Add all" to the cart. Put the Fit Score badge (`Components/`, from Adam) on the sheet: `POST /ai/fit-score {product_ids, closet_item_ids}`.
4. **Onboarding:** height/weight (for `/size`) and the full-body photo (`POST /users/{id}/body-photo`, multipart `file`). Store height/weight locally.
5. Look and feel: app icon, colors, fonts.

### Nabil: Cart + Fit Check tabs (his routes)
1. **Cart:** `GET /cart/{user}`, grouped by store with subtotals and a total; remove with `DELETE /cart/{user}/items/{id}?size=`.
2. **Checkout:** `POST /checkout/{user}`, then a receipt showing each purchase's `status`: `paid`, or `nessie_failed` with a retry. On **409**, `detail` is an object: show `detail.message` and keep the cart. Then `GET /orders/{user}`.
3. **Fit Check feed:** `GET /fitcheck/feed?user_id=` → photo, caption, author, like (`POST .../like`), comment count.
4. **Create a post:** PhotosPicker → multipart `POST /fitcheck` (`user_id`, `file`, `caption`). The AI pre-fills tags; the owner edits them with `PATCH /fitcheck/{id}/tags`.
5. **Post detail:** tags, comments, the **Fit Score badge** (`POST /ai/fit-score {items: post.tagged}`), and **"Shop this fit"** (`GET /fitcheck/{id}/shop?user_id=`): cards with `reason` and Add to Cart.

### Adam: Core + Closet + Profile + shared AI pieces
1. Keep `Core/API.swift` and `Models.swift` in sync with the backend, and review `Core/` PRs.
2. **Closet:** `GET /closet/{user}` grid; upload via PhotosPicker → `POST /closet/upload`. If `duplicate_of` is set: "Looks like you already have this" → **Keep both** / **Remove** (`DELETE /closet/{user}/{id}`).
3. **Profile:** the Style DNA card (`GET /users/{id}/style`: headline, style shares, palette swatches from `hex`, formality, price ranges) with a "Use these budgets" button (`POST /users/{id}/style/apply`). The Settings screen links from here.
4. **Fit Score badge** component (`score` + `verdict`; tap shows `notes`), used by Ryan and Nabil.

## Timeline

| When | Goal |
| --- | --- |
| **Fri night** | Starter merged to `staging`. Everyone builds and runs it against the live backend and starts their tab 1 task. |
| **Sat noon** | **End-to-end on a phone:** feed → size → add to cart → checkout `paid` (Ryan + Nabil). Closet upload works (Adam). |
| **Sat evening** | Try-on, complete the look, Fit Check post + shop the fit, Style DNA, Fit Score. Real fits photographed at the venue for Fit Check. |
| **Sat night** | Polish, empty/error states, demo script, devpost write-up. |
| **Sun morning** | Feature freeze, record a backup demo video, submit. |

## Paste-in brief for your coding agent

> Repo `latrael/dresstoimpress`, branch from `staging`. The iOS app is in `ios/` (SwiftUI, iOS 17, no third-party packages). Read `docs/ios-plan.md`, `ios/README.md`, `ADAM_TO_RYAN.md`, `NABIL_TO_RYAN.md` and `RYAN_TO_NABIL.md` first. My part: **<your section above>**. Only edit `ios/DressToImpress/Features/<my folder>/` (and `Components/` for shared views I own). Use the `API` client in `Core/`. If a call or field is missing, tell me instead of editing `Core/`. Never call `/swipe` for photo paging or vertical browsing. Never put the backend URL or key in code. Build with `xcodebuild -project ios/DressToImpress.xcodeproj -scheme DressToImpress -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build` before each PR into `staging`.
