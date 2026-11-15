# ChatGPT plan Study Agent implementation and verification

## Scope

This slice adds a ChatGPT-plan Study Agent to the packaged Electron app. The existing local question-analysis flow remains separate. A local Study Agent provider is deferred. The old `/agent` route and its unused frontend caller were removed because the route had a mismatched request contract and returned success-shaped errors; existing question-analysis routes and data remain intact.

The Study Agent has no file ingestion, remote proxy, hosted tools, or saved chat history. Each inference requires a checked consent box. The consent text states that the typed message and bounded local summary are sent to OpenAI. The summary contains pending/scheduled counts, up to eight subject/topic/tag summaries, and up to eight topic practice aggregates (set count, net, accuracy); it omits saved question-record text/images and prior chats. Responses use the selected model discovered from the signed-in account, the Responses API, `store: false`, streaming, and no previous-response/history parameter. Errors and cancellation stay visible; there is no provider fallback.

## OpenAI protocol sources

Implementation follows the official documentation only:

- [Sign in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in) — dynamic OSS client registration, loopback callback, PKCE, state, nonce, and consent.
- [Profiles and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) — stable host identity, issued client ID reuse, refresh-token rotation, revocation, and account lifecycle.
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) — account model discovery and Responses API plan usage.
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) and [errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) — eligibility, usage limits, and failure behavior.
- [OpenAI SIWC cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) — protocol overview.

The implementation uses the SIWC-documented fixed authorization endpoint (`https://auth.openai.com/api/accounts/authorize`), token endpoint (`https://auth.openai.com/api/accounts/oauth/token`), and OpenAI JWKS. It uses OIDC discovery only for the revocation endpoint, as directed by the SIWC profiles/sessions guide. The metadata issuer must exactly match `https://auth.openai.com`; the revocation endpoint must be an absolute HTTPS URL on that exact origin with no user info, query, or fragment. Valid metadata is cached in memory; failed or malformed discovery is not cached and prevents any revocation request. Requested scopes are `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`; the implementation requires `openid`, `offline_access`, `resource.invoke`, and `chatgpt.tokens.use.direct` in the grant before enabling inference.

The OAuth flow runs in Electron's main process. It binds a temporary callback to `127.0.0.1`, uses fresh PKCE S256/state/nonce, validates callback state and the issued client ID, and validates the RS256 ID token against OpenAI JWKS (issuer, audience, expiry, issue time, nonce, and subject). It uses no API key, Codex CLI credential, embedded client secret, server proxy, or browser-held token.

## Token lifecycle and account behavior

Tokens are encrypted with Electron `safeStorage` in a user-owned application data file written atomically with owner-only permissions. Linux storage is accepted only when Electron reports a supported system-backed store (`gnome_libsecret`, `kwallet`, `kwallet5`, or `kwallet6`); `basic_text` and unavailable encryption fail closed. After first registration, the newly issued client ID is persisted as soon as the loopback callback state/client ID checks pass, before exchanging the one-time code; a failed exchange can then retry with the issued ID. Refresh is serialized and rotated credentials are persisted. Sign-out attempts the OIDC revocation endpoint with the refresh token and issued client ID, clears local token fields, and retains the non-secret account/client mapping and stable host ID for the next authorization. The UI reports when remote revocation was not confirmed. “Use a different account” explicitly removes the saved mapping after tokens have been cleared.

Automated tests mock Electron secure storage and all OpenAI endpoints. Packaged Electron `safeStorage` behavior has now been verified on Ubuntu 22.04 and Windows Server 2022 in CI (details below). A real subscription sign-in/inference/revocation and installation checks on consumer Windows/Linux desktops remain manual verification items.

## Verification

All automated work used mocks or local deterministic study fixtures; no ChatGPT or local model call was made.

- Desktop at PR #8: `npm test` — 22/22 passed. The follow-up hardening checks below add metadata, IPC, timer, and recovery coverage.
- Frontend: `npm test` — 16/16 passed; `npm run build` passed after adding the recovery UI.
- Backend: `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python -m unittest discover -s backend/tests -v` — 93/93 passed.
- Production UI: `npm run build` — passed.
- Public docs: `npm run test:docs` with `PLAYWRIGHT_CHROMIUM_EXECUTABLE` set to the host's Nix Chromium — passed; English default, Turkish navigation, mobile layout, and no external requests.
- Browser smoke: `npm run test:browser` with the same Chromium path and the temporary backend venv — passed, including mocked Study Agent consent, streaming, cancellation, revocation warning, account-reset flow, and Turkish UI. Reported `ai_included: false`.
- Docs smoke: `npm run test:docs` with the host Chromium path — passed in English and Turkish, including the new unreadable-credential recovery guidance. The extended app browser smoke also exercised the confirmed local-recovery UI with a mocked desktop bridge and reported `ai_included: false`.
- `git diff --check` — passed.

## Follow-up hardening for PR #9

The SIWC documentation distinguishes fixed authorization/token endpoints from revocation discovery. The implementation now validates and caches only the discovered revocation endpoint; authorize, token, and JWKS remain fixed to the documented SIWC endpoints. Mock tests exercise valid discovery, cache reuse, retry after a network failure, malformed/missing metadata, untrusted issuer/origin/scheme/type, and prove no token is POSTed to a metadata-provided URL. Another test confirms callback timeout cleanup when the system browser cannot be opened.

Unreadable encrypted credentials now produce a recoverable status. The user must explicitly confirm removal of the unreadable file; the stable host ID is retained, the UI says remote revocation could not be confirmed, and a readable active credential record cannot use this recovery action. The IPC trust/consent boundary is now directly tested through mocked registered main-process handlers, including off-origin and subframe denial, explicit-consent denial, and per-WebContents cancellation/delta routing.

- Desktop: `npm test` — 29/29 passed with mocked Electron and endpoint dependencies; no real ChatGPT/local model calls.
- Frontend: `npm test` — 16/16 passed; `npm run build`, `npm run test:docs`, and `npm run test:browser` passed, including the new localized recovery action. Browser smoke reported `ai_included: false`.
- Native Electron secure-store behavior, real SIWC sign-in/inference/revocation, and consumer-machine recovery UX were not exercised and remain manual checks.

The smoke fixture uses a fixed November 14 date. On the first PR CI run the app date was November 14, so the question became scheduled and the due-only review card was hidden; the smoke incorrectly required that card. On this host the app date was November 15, so the same question was due and the old scheduled-summary assertion also failed. The smoke now verifies the persisted per-question attempt API result across reload, independent of current date. The browser run uses the host's Nix Chromium because Playwright's bundled Chromium could not load the system library `libglib-2.0.so.0`.

## AI-free benchmarks

All commands ran sequentially with Python 3.14.8 on Linux, logical CPU count 8, seed `20261114`. Each JSON result reports `ai_included: false` and passed its correctness assertions.

| Benchmark | Result |
| --- | --- |
| `benchmark_storage.py` | 1,000 exam records; sequential append 16.1758 s (61.82 records/s); warm read p50 0.011233 s. This is explicitly a growing-JSON rewrite stress case. |
| `benchmark_questions.py` | 24 synthetic image-backed questions; upload 1.1248 s; text capture 0.1613 s (148.76/s); local upload/list/insight/edit/attempt/review/delete assertions passed. |
| `benchmark_backup.py` | 24 files / 25,186,280 upload bytes; export p50 0.954507 s; validation p50 0.118225 s; restore p50 0.118633 s; hashes and restored data matched. |
| `benchmark_question_order.py` | 1,000 questions: warm full summary p50 0.024770 s; 10,000 questions: 0.278900 s; oracle checks passed. |
| `benchmark_practice_sessions.py` | 1,000 sessions: warm full summary p50 0.036181 s; 10,000 sessions: 0.366359 s; topic/session counts matched. |
| `benchmark_mixed_workloads.py` | Persisted 1,500 exams, 2,500 questions, and 4,000 practice sessions; question insight p50 0.116163 s, practice summary p50 0.130388 s; concurrency, mutation, progression, review, and trend oracles passed. |

Benchmark command form: `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python backend/benchmarks/<benchmark>.py --json-output /tmp/hamartia-siwc-<name>.json`.

## Remaining manual checks

- Complete a real eligible ChatGPT account authorization, inference, cancellation, sign-out/revocation, and reauthorization on a user's desktop.
- Verify packaging and persisted app data on consumer Windows 10/11 and a separate Debian desktop.
- A local Study Agent provider is a separate future phase. Do not run local model checks in CI or benchmarks.

## Native `safeStorage` package CI

For PR #12 at `1721f69f103bfac5c1d7ca3a5b0960cc5133623d`, the [Desktop package builds workflow](https://github.com/Nec0ti/hamartia/actions/runs/43657125686) completed successfully. The [Ubuntu 22.04 job](https://github.com/Nec0ti/hamartia/actions/runs/43657125686/job/132638028706) and [Windows Server 2022 job](https://github.com/Nec0ti/hamartia/actions/runs/43657125686/job/132638028508) passed, as did the [full Hamartia checks](https://github.com/Nec0ti/hamartia/actions/runs/43657122049) and [repeat full checks](https://github.com/Nec0ti/hamartia/actions/runs/43657125695) for that head.

- Ubuntu packaged-app smoke reported `gnome_libsecret`, encryption available, a successful in-memory encrypt/decrypt round-trip, and protected credential storage available. The isolated `--password-store=basic` run reported `basic_text`, encryption unavailable, no round-trip, and protected credential storage unavailable. Both assertions passed. The Debian package install/launch/removal and AppImage launch smokes also passed with the protected GNOME keyring.
- Windows packaged-app and installed NSIS-app smokes both reported `win32`, encryption available, a successful in-memory round-trip, and protected credential storage available. Electron's Windows `safeStorage` implementation uses DPAPI ([Electron `safeStorage` documentation](https://www.electronjs.org/docs/latest/api/safe-storage)).
- The smoke used a random in-memory value and exposed only platform/backend/availability/round-trip/policy metadata. It verified that no ChatGPT credential or host-ID file was created. It did not access a user's keychain, sign in to an account, or call an AI provider.

This establishes the native storage behavior in those CI package environments. It does not replace real-account checks or testing on consumer Windows 10/11 and a separate Debian installation.
