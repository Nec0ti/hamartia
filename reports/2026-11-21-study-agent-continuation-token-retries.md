# Study Agent continuation retry safety

## Behavior

All five signed continuation flows (branch exam, sectioned TYT/AYT, user-defined custom exam, learning evidence, and missed question) now reserve a token atomically while processing a continuation. A second concurrent request using the same token is rejected. A failed expected-field/claim validation or provider preparation releases the reservation, allowing the same turn to be retried. A successfully produced draft commits the token, so later replay is rejected.

Reservation state is process-local and bounded to 4,096 token hashes per flow. The original HMAC, expiry, transcript, profile, schema, and quote checks remain in place. Only SHA-256 token digests are kept in the replay cache; no transcript or signed token is persisted. PracticeSession capture has no signed continuation token and is unaffected. Data models, backup format, and restore behavior are unchanged.

A completed draft response lost before it reaches the app remains a retry boundary: the handler has committed the token, so replay is rejected and the capture must be restarted. No completed-response cache was added, avoiding extra retention of transcript-derived drafts. This is not exactly-once response delivery.

## Verification

- Backend suite: `PYTHONPATH=backend python -m unittest discover -s backend/tests -v` — 306 passed, 1 platform-specific Windows test skipped.
- Focused retry tests: 4 passed. They cover all five composed workflows retrying after expected-field rejection and mocked provider error, successful replay rejection, LearningEvidence/Question quote rejection followed by retry, one in-flight concurrent duplicate request, and atomic reservation release/commit behavior.
- Provider-free backend benchmark matrix: 16 commands passed, including all five Study Agent host-flow benchmarks. Provider/model execution was excluded by fail-fast tripwires; benchmark records reported `ai_included: false`.
- No real provider/model was executed. The request tests use mocks only.
- EN/TR Study Agent guides document retry behavior and the response-loss boundary.
- Frontend tests: 63/63; desktop tests: 58/58; frontend production build passed (existing large-chunk warning).
- Offline docs integrity benchmark passed: 17 rendered pages per language, 1,064 local links/assets, zero errors; `ai_included: false`, no network.
- Frontend Clock and focused-practice helper benchmarks passed with provider/model execution disabled and zero network attempts.
- Browser-backed docs/onboarding/dashboard smoke and dashboard UI benchmark could not start Chromium because this NixOS environment lacks `libglib-2.0.so.0`. Desktop Linux/Windows package builds were not run locally; exact-head package CI remains the package gate.

No local live provider/model execution occurred. CI uses isolated hosted runners for the browser and package checks.
