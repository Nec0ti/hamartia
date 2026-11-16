# Study Agent LearningEvidence tool flow

Date: 2026-11-16
Scope: a private, local LearningEvidence entry workflow that uses the existing Study Agent providers. This is a host-side correctness slice, not a claim of legal, hosting, or broader launch readiness.

## Behavior and trust boundary

- The configured endpoint and ChatGPT Responses adapter receive the current conversation and may return only `field` plus exact `quote` hints. Their tool arguments cannot submit record values, dates, completion state, mastery, user IDs, or URLs as values.
- Hamartia owns the transcript, language, expected field order, follow-up question, parsing, field validation, source offsets, preview digest, and create request. A quote must occur exactly once in a student turn and match the host's next expected field. Missing or ambiguous facts produce a localized follow-up and no preview.
- Activity is stored as the student's qualified self-report verbatim. “I worked on chapter 2” and “I completed chapter 2 except the final section” remain those exact statements; the workflow does not upgrade them to whole-task completion or mastery. Negated, hypothetical, uncertain, and future activity claims do not produce an approvable preview.
- The date must appear explicitly in valid `YYYY-MM-DD` form. An optional HTTP(S) URL must be an exact, unique quote in the conversation. URL text with ambiguous trailing punctuation is rejected rather than normalized. URLs are validated locally and never fetched.
- The exact canonical preview requires separate explicit approval. Create recomputes the evidence and digest, then performs the append while holding the shared storage mutation lock. Same-body retries return the existing row; altered requests with the same approval ID return 409. A user deletion retains only that random approval UUID in `learning_evidence_agent_approvals.json`; replay after deletion returns 409 and cannot recreate the row. This content-free ledger is included in local backups and grows by one UUID for each deleted agent-created entry.
- Manual LearningEvidence CRUD remains unchanged. The conversation is not stored by Hamartia, no social upload/sync was added, and no provider can write directly.

## Verification

Tests mock both provider adapters; no real provider credentials, network AI calls, or local model execution were used. The deterministic host benchmark fail-fast patches provider-facing `AIService` entry points and checks full stored rows, exact quote offsets, digest and approval fingerprints, same-body replay, altered replay conflict, eight-way concurrent idempotency, and invalid/hypothetical no-write behavior.

Latest local results:

- Full backend suite: 247 tests run, 238 passed, 9 PostgreSQL integration tests skipped because local `HAMARTIA_SOCIAL_TEST_DATABASE_URL` is unset. CI provisions PostgreSQL 17 and runs the full suite.
- Focused LearningEvidence, manual CRUD, and backup tests: 37 passed; backup checks cover ledger round-trip and legacy archives without the optional ledger.
- Frontend: 63/63 tests passed; production build passed with the existing large-chunk warning. Desktop: 67/67 tests passed, including mocked ChatGPT tool/IPC paths.
- The Playwright browser smoke now includes a LearningEvidence interaction flow: mock ChatGPT tool responses only, EN invalid/incomplete follow-up, EN preview cancel with zero create requests, and TR follow-up/preview/approval with one create whose fields, quote provenance, and digest match the exact host preview. `node --check frontend/_smoke.cjs` passes. The full browser run cannot be completed locally because Chromium lacks `libglib-2.0.so.0`; CI's `npm run test:browser` remains required.
- Generated documentation integrity benchmark passed: 17 pages per language, 818 local links/assets, 108 exact evidence excerpts, zero network or AI calls. The local Playwright docs smoke could not start Chromium because this host lacks `libglib-2.0.so.0`; the CI browser job remains required.
- Host-only benchmark, three measured repeats after one warm-up per size:
  - 24 records: p50 0.245252 s, p95 0.266586 s, 90.03 records/s.
  - 64 records: p50 0.769975 s, p95 0.803728 s, 79.63 records/s.
  - Eight concurrent retries produced one row in 0.038534 s (24-record trial) and 0.058429 s (64-record trial).
  - Hypothetical writes: 0. Provider tripwire calls: 0.
- Backup tests confirm the approval UUID ledger round-trips and older backups default it empty.

CI checks remain required before PR approval. CI provisions PostgreSQL 17 for the backend integration suite and runs this host-only benchmark with the other backend benchmarks. The desktop ChatGPT adapter is separately covered by mocked Node tests; the host benchmark does not instantiate either provider adapter. Provider execution, model quality/latency/resource behavior, and physical-device verification are intentionally excluded.

## Limitations

This is a narrow deterministic parser for explicitly self-reported evidence, not independent verification of learning or activity. English/Turkish completion checks are conservative patterns and cannot establish factual truth. The preview is a local application safeguard, not a boundary against a malicious process running as the same OS user. Provider operators may retain conversation data under their own policies. No real account/provider call or deployment was performed.
