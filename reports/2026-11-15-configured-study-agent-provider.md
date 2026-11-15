# Configured Study Agent provider

## Scope

The packaged desktop Study Agent now defaults to ChatGPT and offers the existing Settings endpoint as an explicitly selected optional provider. It reuses the configured OpenAI-compatible URL, model, and API key; the Council-of-Minds question-analysis prompt remains separate. Provider errors do not switch providers. No chat transcript or history is stored.

Before a configured-endpoint request, the user checks consent that names the exact URL and lists the data sent: the typed question, pending/scheduled totals, up to eight topic priorities with subject/topic/pending count/tags, and up to eight practice aggregates with set count/net/accuracy. Saved question-record text/images and past chats are excluded. Consent also discloses when the saved API key is sent for authentication and that the endpoint operator may have separate retention rules. Opening Settings or receiving updated settings clears consent; the accepted settings object is checked synchronously in the UI and its non-secret URL/model/key-presence values are checked against current backend settings before inference.

The backend rejects non-absolute or non-HTTP(S) endpoint URLs and URLs containing user information, query strings, fragments, whitespace, or invalid ports. Other hosts are accepted so a user can choose a LAN endpoint; the UI warns for every non-loopback host and separately warns when HTTP traffic is unencrypted. The app does not claim that a configured service is local or network-isolated. The API key remains backend-side and is not returned to the renderer.

## Verification

- `python3 -m compileall -q backend/app` — passed; syntax compilation only.
- `npm ci --ignore-scripts` — installed the existing frontend lockfile dependencies without lifecycle scripts.
- `npm run build` — passed. Vite reported the existing large-chunk warning; output JavaScript was 749.54 kB minified.
- `git diff --check` — passed.
- No tests, browser smoke checks, or benchmarks were added or run for this provider. No local AI endpoint/model or ChatGPT provider was called.

## Remaining manual work

Try the configured endpoint and model on another computer. Verify the destination and any endpoint-side key handling with the user's chosen service. The configured-endpoint request is not cancellable once submitted; the UI indicates that it is working. ChatGPT account, inference, and native secure-storage checks remain separate manual items.

## Settings startup-race follow-up (PR #14)

Settings are fetched once when the app starts; opening the Settings modal does not start a second fetch. The modal shows a loading status and keeps endpoint, model, API-key, and save controls disabled until that startup fetch settles, so a late initial response cannot replace edits made against placeholder values. Opening Settings still invalidates Study Agent endpoint consent synchronously. Every successful settings PATCH installs the fresh backend response object (including after API-key replacement); consent remains tied to the exact settings object and is checked again before a send. The API returns only `has_api_key`, never the key itself.

Verification for this settings-only follow-up:

- `npm test` — 18/18 passed.
- `npm run build` — passed; Vite reported the existing large-chunk warning (750.87 kB minified JavaScript).
- `npm run test:docs` with Nix Chromium — passed; no external requests.
- `npm run test:browser` with Nix Chromium and the temporary backend environment — passed. The browser smoke delayed the initial `/settings` GET, opened Settings while it was pending, verified API-key and Save controls stayed disabled, then released the response and verified the controls became available. It also confirmed API-key persistence. Output reported `ai_included: false`; this check did not call `/study-agent/local` or any model.
- `git diff --check` — passed.

These checks cover Settings loading and persistence only; they are not a local-provider test or benchmark. Real endpoint/model behavior remains for manual verification on another computer.
