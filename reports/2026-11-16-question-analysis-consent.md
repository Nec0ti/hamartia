# Per-request consent for question analysis

**Status:** implemented and tested with mocked transport. Real model execution, key use, endpoint trust, and multimodal behavior remain manual-only; no provider request or deployment was performed for this change.

## Behavior

- The Questions screen now says **Review with AI** because Settings accepts either local or remote OpenAI-compatible endpoints.
- Clicking it calls only the local Hamartia API for a preview. The bilingual, keyboard-accessible dialog shows the sanitized hostname and effective port, local/remote classification, HTTP/HTTPS scheme, model, analysis instructions, whether saved question/OCR text and filename fields are present, whether saved image bytes are included, and API-key setting/effective-auth categories. It never returns or renders the key, URL path, URL query, or URL userinfo. Endpoint URLs with userinfo, query parameters, or fragments fail closed.
- The user must explicitly approve each request. Cancel, Escape, backdrop close, and the close control send a local cancellation request only; no configured-provider request is made. An affirmative action consumes a one-use approval and makes one provider attempt. The OpenAI client has `max_retries=0` for this flow, so failures are not silently retried.
- Preview snapshots expire after five minutes, are limited to 128 entries and 32 MiB of retained serialized request data, evict oldest entries to remain within the budget, and allow at most two concurrent preview builds. An individual over-budget request returns 413; a busy preview builder returns 429. Dismissed snapshots are released through the local cancel route.
- Approval re-reads the question and settings and compares an internal fingerprint covering the exact prompt (including image bytes), endpoint, model, effective auth value, question ID, and timestamp. A changed request consumes the approval and returns 409 before provider transport. The provider receives the frozen prompt snapshot after a successful comparison.
- Question/OCR text is limited to 65,536 UTF-8 bytes; saved image reads are capped at 10 MiB plus one byte to detect overflow. New question create/edit inputs and settings URL/model/key inputs have corresponding bounds. Oversized legacy data fails preview before prompt construction. The UI maps the 413 response to bilingual guidance.
- Request-validation errors now use one generic `{"detail":"Invalid request"}` response in both ASGI applications. This prevents Pydantic from reflecting submitted API keys or question text in error bodies.

## Verification

- Full backend suite: **226 tests run**, **217 passed**, **9 skipped**. The nine skips are the social PostgreSQL integration cases because this local run did not set `HAMARTIA_SOCIAL_TEST_DATABASE_URL`. The CI backend job provisions PostgreSQL 17, sets that variable, and runs the complete suite.
- Focused question-analysis/question tests: **47/47 passed**; settings and app-factory validation tests: **14/14 passed**.
- Frontend tests: **63/63 passed**. Production build passed; Vite retained the existing warning for the large JavaScript chunk (about 863 kB before gzip).
- Desktop tests: **64/64 passed**.
- Mocked `httpx.MockTransport` failure: exactly one HTTP attempt with `max_retries=0`; no real endpoint was contacted. Route tests prove preview and cancellation do not call provider transport, cancellation/replay returns 409, stale question/settings returns 409, approval calls the provider once, and oversized inputs fail before prompt/provider use.
- Offline bilingual documentation integrity benchmark: 17 routes per locale, 818 local links/assets, 108 evidence excerpts, zero errors; it reports `ai_included: false` and `network_access: false`. Human retrieval/screenshot and separate-device endpoint checks remain pending.
- `git diff --check` passed. No model execution, quality/latency/resource benchmark, real credentials, or network deployment was used.

## Review and release boundary

Commits on the feature branch, in order:

- `3441fe6` — preview and one-use server snapshot gate.
- `22b953e` — sanitized endpoint, retained-byte budget, and bounded preview admission.
- `47dd05e` — bilingual consent dialog and API client.
- `67ec82a` — UTF-8/image/configuration limits and stale-input checks.
- `0bb9ec8` — accessible dialog and localized size guidance.
- `ae2a1fa` — input-redacting 422 responses in both service factories.

No real provider settings were added or changed. No public service, home server, tunnel, or deployment was contacted. The separate-device synthetic-image test remains **NOT RUN** in [the manual verification template](2026-11-15-external-manual-verification-template.md). This slice does not establish public-launch or legal readiness.
