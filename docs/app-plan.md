# App plan: FlutterFlow → plain Flutter

**Decided Fri Oct 23, ~9:15 PM.** FlutterFlow needs a paid plan for API calls, so the app moves to **plain Flutter**: free, and it runs in Chrome with no Xcode.
- **Ryan continues from his existing FlutterFlow work** (same screens, same Quick Browse spec in `RYAN_TO_NABIL.md`) and completes the sections himself. It's not a rewrite from scratch.
- **The iPhone build comes afterward,** on Adam's Mac.
- **The backend doesn't change.** It's HTTPS + JSON with one header; routes are in `ADAM_TO_RYAN.md` and `NABIL_TO_RYAN.md`.

## Setup (15 min, any laptop)

1. **Install the Flutter SDK** (flutter.dev → Get started) and Chrome. Check with `flutter doctor`. Xcode and Android Studio are optional, and `flutter doctor` complaining about them is fine.
2. **Ryan's project:** whatever he carried over from FlutterFlow, run with `flutter run -d chrome`. **Optional reference:** branch `flutter-starter` has a small Dart API client + models for every route (headers, error shapes) to copy from if useful. It's not the app.
3. **Backend:** the tunnel URL and key are sent privately in the group chat. Keep them in a settings screen or a local, untracked config file, never in code.
   - **Never put the URL or key in code or Git**; the repo is public. When Adam restarts the tunnel, paste the new URL in Settings.
4. **Phones:**
   - **Android:** plug in with USB debugging on, then `flutter run`.
   - **iPhone:** only on a Mac with Xcode (Adam's): `flutter run` with the phone plugged in, signed with a free Apple ID (Personal Team). Free certificates last 7 days.
5. **Demo user:** `u_demo`.
6. **Images on web:** product photos load through `GET /img?url=` on our backend, which needs no key. Retailer image servers don't always allow web apps to load their images directly.

**Rules:**
- **Ryan owns the app.** If a call or field is missing, ask Adam (AI routes) or Nabil (commerce routes).
- **Branches:** `app/<you>-<thing>` → PR into `staging`. Before every PR: `flutter analyze` is clean, and it runs in Chrome against the live backend.
- **Never call `/swipe` for photo paging or vertical browsing** (Ryan's rule). Save = `PUT /wishlist/...`. Cart = `POST /cart/.../items`.

## Who builds what

**Ryan owns the whole app** and completes the sections from his FlutterFlow work. Adam and Nabil stay on their backend tracks and answer API questions.

### Ryan: the app, in this order
1. **Feed / Quick Browse + product page.** Match his wireframe: picture section, dots, info, description, size chips, Add to Cart, heart. No `/swipe` for paging or browsing.
2. **Cart → checkout `paid`** (the Saturday-noon checkpoint).
3. **Try it on + Complete the look** (the AI moments judges see).
4. **Fit Check:** feed, post, "Shop this fit".
5. **Closet, Profile / Style DNA, onboarding.**
6. Look and feel: theme, fonts, icon. Empty, loading and error states.
7. **Then the iPhone build** on Adam's Mac (Xcode, free Apple ID).

### Adam: AI backend (his track)
- AI routes and quality, plus anything Ryan needs from the AI side.
- Hosts the backend (Mac + tunnel). Builds and runs the iPhone version once Ryan's sections are done.

### Nabil: commerce backend (his track)
- `/feed` should prefer ranked cards, so every card has a reason. Add fuller Fit Check seed tags (category, color, pattern, style_tags), and keep Nessie checkout solid.
- Owns the README for sponsor judges (Apify, Capital One / Nessie), the Devpost write-up and the demo script.

**Backup rule:** if the noon checkpoint is at risk, Adam or Nabil take one whole tab from Ryan's list, agreed in the group chat. Never a half-shared screen.

## Timeline

| When | Goal |
| --- | --- |
| **Fri night** | Ryan's project runs in plain Flutter (Chrome) against the live backend, starting with the feed. |
| **Sat noon** | **End-to-end:** feed → size → add to cart → checkout `paid`, in Chrome and on a phone. |
| **Sat evening** | Try-on, complete the look, Fit Check post + shop the fit, Style DNA, Fit Score. Real fits photographed at the venue. Then the iPhone build. |
| **Sat night** | Polish, empty/error states, demo script, Devpost write-up. |
| **Sun morning** | Feature freeze, record a backup demo video, submit. |

## Paste-in brief for your coding agent

> Repo `latrael/dresstoimpress`, branch from `staging`. I'm continuing my FlutterFlow app as a plain Flutter project. Read `docs/app-plan.md`, `ADAM_TO_RYAN.md`, `NABIL_TO_RYAN.md` and `RYAN_TO_NABIL.md` first. Work in the order in the plan. Every request needs the `X-DTI-Key` header; URL and key come from a settings screen or an untracked local file, never code. Never call `/swipe` for photo paging or vertical browsing. Load product images through the backend's `/img?url=` on web. Optional: copy the API client/models from branch `flutter-starter`, `app/lib/core/`. If a backend call or field is missing, tell me instead of guessing. Test in Chrome (`flutter run -d chrome`) before each PR into `staging`.
