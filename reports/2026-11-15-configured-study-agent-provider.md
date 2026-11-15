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
