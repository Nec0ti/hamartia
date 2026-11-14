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

The implementation uses the official OIDC discovery document at `https://auth.openai.com/.well-known/openid-configuration` and the discovered OpenAI authorization, token, JWKS, and revocation endpoints. Requested scopes are `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`; the implementation requires `openid`, `offline_access`, `resource.invoke`, and `chatgpt.tokens.use.direct` in the grant before enabling inference.

The OAuth flow runs in Electron's main process. It binds a temporary callback to `127.0.0.1`, uses fresh PKCE S256/state/nonce, validates callback state and the issued client ID, and validates the RS256 ID token against OpenAI JWKS (issuer, audience, expiry, issue time, nonce, and subject). It uses no API key, Codex CLI credential, embedded client secret, server proxy, or browser-held token.

## Token lifecycle and account behavior

Tokens are encrypted with Electron `safeStorage` in a user-owned application data file written atomically with owner-only permissions. Linux storage is accepted only when Electron reports a supported system-backed store (`gnome_libsecret`, `kwallet`, `kwallet5`, or `kwallet6`); `basic_text` and unavailable encryption fail closed. After first registration, the newly issued client ID is persisted as soon as the loopback callback state/client ID checks pass, before exchanging the one-time code; a failed exchange can then retry with the issued ID. Refresh is serialized and rotated credentials are persisted. Sign-out attempts the OIDC revocation endpoint with the refresh token and issued client ID, clears local token fields, and retains the non-secret account/client mapping and stable host ID for the next authorization. The UI reports when remote revocation was not confirmed. “Use a different account” explicitly removes the saved mapping after tokens have been cleared.

Automated tests mock Electron secure storage and all OpenAI endpoints. Native safeStorage behavior, a real subscription sign-in/inference/revocation, and installation checks on physical Windows/Linux desktops remain manual verification items.

## Verification

All automated work used mocks or local deterministic study fixtures; no ChatGPT or local model call was made.

- Desktop: `npm test` — 22/22 passed. Covers PKCE/state/nonce, scopes, consent, token validation/redaction, storage failure, failed code exchange and issued-client-ID reuse, refresh rotation/races, model filtering, Responses streaming/completion, error and quota handling, cancellation, revocation success/failure, and account mapping reuse.
- Frontend: `npm test` — 16/16 passed.
- Backend: `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python -m unittest discover -s backend/tests -v` — 93/93 passed.
- Production UI: `npm run build` — passed.
- Public docs: `npm run test:docs` with `PLAYWRIGHT_CHROMIUM_EXECUTABLE` set to the host's Nix Chromium — passed; English default, Turkish navigation, mobile layout, and no external requests.
- Browser smoke: `npm run test:browser` with the same Chromium path and the temporary backend venv — passed, including mocked Study Agent consent, streaming, cancellation, revocation warning, account-reset flow, and Turkish UI. Reported `ai_included: false`.
- `git diff --check` — passed.

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

- Verify Electron `safeStorage` uses the expected native OS-backed credential store on each supported platform; Linux `basic_text` must stay unavailable.
- Complete a real eligible ChatGPT account authorization, inference, cancellation, sign-out/revocation, and reauthorization on a user's desktop.
- Verify packaging and persisted app data on native Windows and Linux installations.
- A local Study Agent provider is a separate future phase. Do not run local model checks in CI or benchmarks.
