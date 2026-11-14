# Product language and ChatGPT study agent plan

## User direction

- The application offers exactly two UI languages: English and Turkish.
- English is the default for a fresh install, regardless of browser language. Save the user's selection locally.
- Repository prose, code comments, README files, plans, reports, PRs, and future GitHub text use English.
- Public user documentation is published with GitHub Pages in English and Turkish, with English as the default and an explicit language switch. Keep internal planning and development docs off the public site.
- Keep the bilingual release policy and release notes in `RELEASES.md`; other repository Markdown remains English.
- Support Windows 10/11, Debian packages, and AppImage. After each merged PR, create a GitHub Release using a themed sequential code such as `ARETE-001`, not SemVer.
- Add Sign in with ChatGPT for eligible users to power Hamartia's study agent from their ChatGPT plan. Keep the existing local model available as an optional provider; real local-model checks remain a later, separate-computer task.

## Phase 1: English-first bilingual interface and repository

- Add a small English-first translation dictionary and React language context; do not add a large i18n dependency for two locales.
- Add an English/Turkish selector in Settings, persist only `en` or `tr`, fall back to English for invalid values, and update the document `lang` attribute.
- Translate all application copy, accessible names, validation/error messages, chart labels, date/number presentation, and empty/loading states. Keep user-entered subject/topic/tag data and stored API values unchanged.
- Translate every tracked Markdown document and all non-UI code comments to English. Keep the historical commit graph intact; use English for all new commit messages and GitHub content.
- Verify the English fresh-install default, language persistence and reload, representative workflows in both languages, screen-reader labels, mobile layout, frontend tests/build, backend tests, browser smoke, and AI-free benchmarks.

## Phase 1b: Public documentation and desktop delivery

- Build a focused user guide from English source pages and publish English/Turkish versions with GitHub Pages. Include install, first run, data/privacy, backup/restore, AI provider, and release guidance; do not publish backlog, private notes, or internal reports.
- Deploy the Pages artifact automatically from `master`; use GitHub Actions Pages permissions and document the one-time repository setting required to select GitHub Actions as the Pages source.
- Package the existing React/FastAPI app for Windows 10/11, `.deb`, and AppImage. Store app data under the operating system's per-user application data directory and keep the API bound to loopback.
- Add a merged-PR release workflow that builds the supported packages and publishes bilingual notes under sequential themed codes (`ARETE-001`, `ARETE-002`, ...). Treat the first release workflow as the release-pipeline bootstrap; every later merged PR should create a release.
- Verify packaging on native Windows and Linux runners, Pages build/deploy, release version uniqueness, and install/launch/data persistence. Do not claim platform packaging is verified on a platform without a runner.

## Phase 2: ChatGPT-plan study agent

### Integration

- Use the official open-source Sign in with ChatGPT flow for this local application. The user explicitly consents to ChatGPT-plan usage; sign-in identity alone is not treated as permission to run inference.
- Register on first use with the dynamic OSS client flow, a stable opaque per-install host ID, a loopback callback bound to `127.0.0.1`, fresh state/nonce/PKCE values, and the application name. Validate callback state, ID-token signature/issuer/audience/expiry/nonce, and granted inference scopes before activating the account.
- Use the public Responses API with the selected account's OAuth access token. Discover models from that account rather than hardcoding availability. Stream until a completed response; set `store: false`; handle cancellation, auth failure, ineligible accounts, usage limits, network failures, and incomplete responses explicitly.
- Refresh rotating credentials safely and serialize refreshes. Keep credentials out of React, `settings.json`, backups, source control, logs, analytics, and test reports. Persist them only in a protected local credential store with owner-only access; fail closed if the platform cannot provide the configured protection.
- Add a small Turkish/English Study Agent screen. It follows the selected UI language and can use a narrow, read-only set of local study tools/context. Show when the ChatGPT plan is in use and link to usage settings. Explain that only the supplied chat/context is sent to OpenAI and that ChatGPT conversations are not imported.
- Keep the existing local model as a separately selectable option for existing question review; never silently switch providers after an error. Real local model testing stays out of CI and benchmarks.

### First release boundary

- Implement the ChatGPT-backed study agent first. Do not expand the initial sign-in change into general ChatGPT account sync or importing ChatGPT conversation history.
- Preserve current question/exam/practice JSON data and backups. Chat messages are not added to exam or mistake records unless a later product decision defines that behavior.
- Do not expose shell, filesystem, network, or data-mutating tools to the study agent. Local tools only return explicitly scoped study context.

### Verification

- Mock OAuth and Responses API calls in automated tests; never use a real ChatGPT account/model in CI or benchmarks.
- Test PKCE/state/nonce and ID-token validation, consent denial, missing scope, token redaction, secure-store failure, refresh rotation/races, cancellation, API/quota errors, and no silent local-provider fallback.
- Browser smoke covers English/Turkish switching and mocked sign-in/status/chat/error flows. A real subscription login and response is a manual check on the user's machine and must not leave real tokens in the repository.

## Sequence and completion gate

1. Finish and merge the current local-first study workflow PR (already merged as PR #1).
2. Implement Phase 1 in its own PR; merge only after CI passes.
3. Implement public bilingual docs, GitHub Pages, desktop packages, and the automatic release pipeline in a delivery PR; merge only after the relevant CI checks pass and the Pages source is configured.
4. Implement Phase 2 in its own PR; merge only after mocked checks and CI pass.
5. Keep real account/model checks manual. The project is not ready to claim account integration works until the user completes that manual verification.

## Main risks

- Sign in with ChatGPT open-source plan usage currently applies to eligible accounts and is a distinct consent from identity. Availability, plan policy, and usage limits can differ by account/workspace and may change.
- Refresh tokens are long-lived secrets. Credential storage and loopback OAuth validation are security boundaries.
- Hamartia currently runs as a local web app rather than an Electron application; the backend must own the OAuth callback and token custody, while the browser receives status/results only.
- The current `/agent/chat` implementation has no UI, a JSON/form contract mismatch, and turns errors into success-shaped fallback replies. Fix all three before presenting a ChatGPT agent as usable.
