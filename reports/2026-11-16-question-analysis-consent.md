# Per-request consent for question analysis

**Status:** implemented and tested with mocked transport. Real model execution, key use, endpoint trust, and multimodal behavior remain manual-only; no provider request or deployment was performed for this change.

## Behavior

- The Questions screen now says **Review with AI** because Settings accepts either local or remote OpenAI-compatible endpoints.
- Clicking it calls only the local Hamartia API for a preview. The bilingual, keyboard-accessible dialog shows the sanitized hostname and effective port, local/remote classification, HTTP/HTTPS scheme, model, analysis instructions, whether saved question/OCR text and filename fields are present, whether saved image bytes are included, and API-key setting/effective-auth categories. It never returns or renders the key, URL path, URL query, or URL userinfo. Endpoint URLs with userinfo, query parameters, or fragments fail closed.
- The user must explicitly approve each request. Cancel, Escape, backdrop close, and the close control send a local cancellation request only; no configured-provider request is made. An affirmative action consumes a one-use approval and makes one provider attempt. The OpenAI client has `max_retries=0` for this flow, so failures are not silently retried.
- Question edit fields and per-question mutation controls are disabled while the approved analysis request is in flight. The backend freshness check remains authoritative across other clients and requests.
- Preview snapshots expire after five minutes, are limited to 128 entries and 32 MiB of retained serialized request data, evict oldest entries to remain within the budget, and allow at most two concurrent preview builds. An individual over-budget request returns 413; a busy preview builder returns 429. Dismissed snapshots are released through the local cancel route.
- Approval re-reads the question and settings and compares an internal fingerprint covering the exact prompt (including image bytes), endpoint, model, effective auth value, question ID, and timestamp. A changed request consumes the approval and returns 409 before provider transport. The provider receives the frozen prompt snapshot after a successful comparison.
- After the provider returns, persistence recomputes the current question/settings fingerprint inside the storage list-mutation callback, while the shared data-directory mutation lock and question-file lock are held. This makes the final compare-and-set atomic against question edits and settings changes. A stale response returns 409 and leaves the record untouched.
- Since the mistake tag is editable but does not affect the approved prompt, the short-lived snapshot retains only `tag_at_preview` (bounded to 128 UTF-8 bytes), separate from the minimal question ID/timestamp record. Analysis save applies the model tag only if current tag still equals both preview-time and dispatch-time values; otherwise it saves the analysis while preserving the latest manual tag.
- Later edits to prompt-source fields (OCR text, image filename, or image path) clear the prior analysis in the same atomic question update. The AI-derived tag resets to the default only when it still matches the old verdict; a differing manual tag override is retained. Subject/topic/curriculum-only edits preserve analysis. The current API does not replace an image on an existing question; uploaded images create their own question record.
- Question/OCR text is limited to 65,536 UTF-8 bytes; saved image reads are capped at 10 MiB plus one byte to detect overflow. New question create/edit inputs and settings URL/model/key inputs have corresponding bounds. Oversized legacy data fails preview before prompt construction. The UI maps the 413 response to bilingual guidance.
- Request-validation errors now use one generic `{"detail":"Invalid request"}` response in both ASGI applications. This prevents Pydantic from reflecting submitted API keys or question text in error bodies.

## Verification

- Full backend suite after stale-result invalidation and all four race tests: **234 tests run**, **225 passed**, **9 skipped**. The nine skips are the social PostgreSQL integration cases because this local run did not set `HAMARTIA_SOCIAL_TEST_DATABASE_URL`. The CI backend job provisions PostgreSQL 17, sets that variable, and runs the complete suite.
- Focused question endpoint tests: **54/54 passed**; consent registry tests: **6/6 passed**; settings and app-factory validation tests: **14/14 passed**.
- Frontend tests: **63/63 passed**. Production build passed; Vite retained the existing warning for the large JavaScript chunk (about 863 kB before gzip).
- Desktop tests: **64/64 passed**.
- Mocked `httpx.MockTransport` failure: exactly one HTTP attempt with `max_retries=0`; no real endpoint was contacted. Route tests prove preview and cancellation do not call provider transport, cancellation/replay returns 409, stale question/settings returns 409, approval calls the provider once, and oversized inputs fail before prompt/provider use. Deterministic blocked-provider tests approve prompt A, then PATCH the question to prompt B or change endpoint settings while the provider is suspended; each request returns 409, no analysis is saved, and there is exactly one provider invocation. A manual-tag test changes the tag while the provider is suspended and proves the analysis is saved once without overwriting that tag. Another regression starts with a non-default tag at preview, changes it back to the default before dispatch, and proves the preview-time tag transition is retained while analysis saves. Separate edit tests prove OCR changes clear stale analysis, unrelated metadata changes preserve it, image filename/path are prompt-source fields, and manual tag overrides survive invalidation.
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
- `0f9283b` — bilingual docs, manual verification, and roadmap/report updates.
- `4ee0823` — atomically reject provider results when question or endpoint settings change in flight.
- `23cca11` — disable question edits and other question mutations while analysis is busy.
- `1559066` — document the compare-and-set and first race regression evidence.
- `9037bb9` — invalidate stale analysis after prompt-source edits and prove settings mutation races.
- `8c6a2b1` — document source invalidation and settings race evidence.
- `db75f55` — preserve manual tag changes during an in-flight analysis save.
- `7364c2b` — document manual-tag race protection.
- `15c841b` — retain the bounded preview-time tag separately and cover the preview-to-dispatch transition.

No real provider settings were added or changed. No public service, home server, tunnel, or deployment was contacted. The separate-device synthetic-image test remains **NOT RUN** in [the manual verification template](2026-11-15-external-manual-verification-template.md). This slice does not establish public-launch or legal readiness.
