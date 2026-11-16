# Social sign-in and private profile UI prototype

**Status:** implementation prototype only. Current builds have no social provider configuration and remain disabled. This is not legal advice, an approved agreement, or launch readiness.

## Scope and design

- Added bilingual sign-in/profile onboarding using the existing private `/social/me/profile` API. Profile values remain user-entered; built-in avatar presets only; there is no public profile route or local-study-data sync.
- In Electron, Google OAuth runs in the system browser with state, PKCE S256, and a one-use `127.0.0.1` callback. The main process exchanges the Google credential with Firebase using the installed Node SDK and explicit in-memory persistence. Tokens stay in main and are not returned to React, logged, or persisted.
- Browser development uses Firebase popup and in-memory persistence, with an optional loopback Auth Emulator. Both flows use a fixed social API origin, the exact profile GET/PATCH routes, `redirect: 'error'`, and no-store caching. The Electron preload exposes only `signIn`, `getProfile`, `patchProfile`, and `signOut`; it rejects untrusted frame origins.
- Vite generates `social-public-config.json` from public build settings and packages it as an Electron extra resource. Missing or invalid configuration fails closed. The current artifact contains empty values. No client secret or user credential is part of the generated file.
- Social profile context remains excluded from Study Agent requests. The existing local study auth and API are unchanged.

## Agreement acknowledgement and release gates

The UI has an unchecked acknowledgement with separate English/Turkish User Agreement and Privacy and consent links. The User Agreement pages are versioned `v0.1-draft` placeholders marked unapproved; the social profile guide describes prototype behavior. No reviewed agreement version is configured, and sign-in remains disabled by default. A matching reviewed version is required by the client and Electron IPC before sign-in or profile GET/PATCH. Sign-out remains available without agreement so it can clear in-memory state and cancel a pending OAuth callback.

This is an app-level pre-auth acknowledgement only. There is no server-side consent receipt or audit record, and a custom client can call Firebase Authentication and the social API outside the UI. It is not legal protection. Real sign-in must remain disabled until reviewed agreement text/version, provider configuration, API host, qualified legal/privacy review, and network/host gates are resolved. No current live provider/project/API configuration was used or verified.

Build variables are public identifiers/settings, not secrets:

- Browser development: `VITE_SOCIAL_ENABLED`, `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`, and `HAMARTIA_SOCIAL_API_TARGET`; optional `VITE_FIREBASE_AUTH_EMULATOR_URL` must be a loopback HTTP origin.
- Electron package build: `HAMARTIA_FIREBASE_API_KEY`, `HAMARTIA_FIREBASE_AUTH_DOMAIN`, `HAMARTIA_FIREBASE_PROJECT_ID`, `HAMARTIA_FIREBASE_APP_ID`, `HAMARTIA_GOOGLE_OAUTH_CLIENT_ID`, and `HAMARTIA_SOCIAL_API_ORIGIN`.
- Both paths additionally require their explicit agreement review flag and version (`VITE_SOCIAL_AGREEMENT_REVIEWED` / `VITE_SOCIAL_AGREEMENT_VERSION` or `HAMARTIA_SOCIAL_AGREEMENT_REVIEWED` / `HAMARTIA_SOCIAL_AGREEMENT_VERSION`). Leave these unset until qualified review approves complete, matching documents. There is no Google client secret.

## Verification

- Frontend tests: **48/48 passed**; desktop tests: **61/61 passed**.
- Production frontend build passed. It emitted the empty social config and strict production CSP; Vite reported the existing large-chunk warning.
- Bilingual documentation integrity benchmark passed: 17 EN and 17 TR navigable pages, 818 local links/assets, no errors. The new versioned agreement pages are standalone `.html` routes and are linked from both privacy guides and the UI. Local Chromium-based docs smoke could not launch because `libglib-2.0.so.0` is absent; CI installs browser dependencies.
- Offline social client benchmark passed on Linux x86_64, Node v26.12.1, Firebase JS SDK 13.3.0. It uses a local fake Auth endpoint, mock OAuth callback/token exchange, and an in-memory profile fixture—not live Google/Firebase or PostgreSQL. Before consent, missing/stale versions produced zero OAuth, Auth Emulator, and profile calls. Accepted-flow measurements: 30 sign-in samples p50/p95/p99 **7.423/10.961/15.867 ms**; 48 profile PATCH+GET samples **2.901/7.368/8.575 ms**; 96 concurrent round-trips across 12 workers **31.415/84.207/114.778 ms**. The network guard allowed 57 loopback connections and rejected all external destinations. The separate profile report covers PostgreSQL API measurements.
- `git diff --check` passed. No live provider, external credential, public service, or local AI call was made.

These are local harness timings, not production performance claims. Real Google latency, availability, provider restrictions, consent UI, network/API-host behavior, and desktop package usability remain unverified.

## Primary implementation references

- [Google OAuth for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Firebase Google sign-in](https://firebase.google.com/docs/auth/web/google-signin)
- [Firebase Auth persistence](https://firebase.google.com/docs/auth/web/auth-state-persistence)
- [Firebase Auth Emulator](https://firebase.google.com/docs/emulator-suite/connect_auth)
- [Social profile and hosting plan, including open launch gates](2026-11-16-social-profile-and-hosting-plan.md)
