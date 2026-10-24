# App plan: plain Flutter

**Decided Fri Oct 23, ~9:15 PM.** FlutterFlow needs a paid plan for API calls, so the app is plain Flutter. Ryan approved this (RYAN_TO_ADAM.md).
- **Ryan owns the app and its design: every screen, layout, flow and visual choice.** This plan covers only who does what, the shared plumbing and the team checkpoints. The design references are Ryan's wireframe and `frontend/QUICK_BROWSE.md`.
- **The backend doesn't change.** Routes and what they return: `ADAM_TO_RYAN.md` (AI) and `NABIL_TO_RYAN.md` (commerce).

## Where the code lives

| Branch | What | Owner |
| --- | --- | --- |
| `RyanFrontendking` | Ryan's app work: `app/lib/features/...` + tests. **Ryan asked to keep this branch.** | Ryan |
| `flutter-starter` | Shared shell and core under `app/`: `pubspec.yaml`, a bare `main.dart` + settings, `lib/core/api.dart` (every route, `X-DTI-Key`, errors, `/img` helper), `lib/core/models.dart`. Ryan's Feed drops in unchanged. | Adam keeps `core/` in sync with the backend; the shell's look is Ryan's |
| `adam/ai-pipeline` | AI backend | Adam |
| `nabil` | Commerce backend | Nabil |
| `staging` | Where everything meets; PRs go here, never to `main` | everyone |

## Setup (any laptop)

1. **Install the Flutter SDK** (3.47.x) and Chrome. Xcode/Android are only needed for phone builds.
2. **Get the code:** `RyanFrontendking` with `flutter-starter` merged in. Then `cd app && flutter pub get && flutter run -d chrome`.
3. **Backend URL and key:** sent privately in the group chat, entered on the device. **Never put them in code or Git** (the repo is public). The URL changes when Adam restarts the tunnel.
4. **Web images:** use the backend's `GET /img?url=` (no key); retailer image servers refuse direct loads from a web app.
5. **iPhone:** built on Adam's Mac after the iOS 26 platform is installed in Xcode (Settings → Components). Free Apple ID; certificates last 7 days.

## Who does what

- **Ryan: the app.** He works through his own pending list (RYAN_TO_ADAM.md): live Feed adapter, size advice, product detail, try-on, complete-the-look / Fit Score, onboarding, then phone verification, in the order and form he decides.
- **Adam: AI backend + hosting.**
  - Keeps `app/lib/core` matching the backend, and adds any call or field Ryan asks for.
  - Keeps the Mac and tunnel up and the AI budget topped up.
  - Does the iPhone build when Ryan is ready.
- **Nabil: commerce backend.**
  - Feed ranking, cart/checkout/Nessie, Fit Check, users/onboarding and search routes.
  - The README for sponsor judges, the Devpost write-up and the demo script.
- **Backup rule:** if a checkpoint is at risk, Ryan decides whether to hand off a whole screen and to whom.

**Rules:**
- PRs into `staging` only.
- Handoffs go in the directional `.md` files on `staging` (Ryan's policy).
- No secrets in the repo.
- Never call `/swipe` for photo paging or passive browsing (Ryan's rule).

## Team checkpoints

| When | Checkpoint |
| --- | --- |
| **Fri night** | `flutter-starter` + Ryan's Feed build together, and the Feed runs in Chrome against the live backend. |
| **Sat noon** | End-to-end on a phone: feed → save / add to cart → checkout `paid`. |
| **Sat evening** | AI features reachable in the app (size, try-on, complete the look, Fit Check shop). Real fits photographed at the venue. iPhone build. |
| **Sun morning** | Feature freeze, backup demo video, submit. |
