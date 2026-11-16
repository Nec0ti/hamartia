# Study Agent LearningEvidence tool flow

Date: 2026-11-16
Scope: a private, local LearningEvidence entry workflow that uses the existing Study Agent providers. This is a host-side correctness slice, not a claim of legal, hosting, or broader launch readiness.

## Behavior and trust boundary

- The configured endpoint and ChatGPT Responses adapter receive the current conversation and may return only `field` plus exact `quote` hints. Their tool arguments cannot submit record values, dates, completion state, mastery, user IDs, or URLs as values.
- Hamartia owns the transcript, language, expected field order, follow-up question, parsing, field validation, source offsets, preview digest, and create request. A quote must occur exactly once in a student turn and match the host's next expected field. Missing or ambiguous facts produce a localized follow-up and no preview.
- Multi-turn state is carried in a host-signed HMAC token containing only verified field/quote claims, locale, message count, and a digest of the prior transcript. The random signing key is per process, so restart invalidates outstanding tokens. Tokens expire after one hour, bind to exactly one appended turn, and are single-use; tampering, expiry, a changed prefix, wrong turn count, or replay returns a conflict. A lock protects a bounded 4,096-entry replay ledger; at capacity continuation fails closed. Caller-supplied prior claims are rejected. Tokens and transcript content are not logged or persisted by the service.
- Activity is stored as the student's qualified self-report verbatim. “I worked on chapter 2” and “I completed chapter 2 except the final section” remain those exact statements; the workflow does not upgrade them to whole-task completion or mastery. Negated, hypothetical, uncertain, and future activity claims do not produce an approvable preview.
- The date must appear explicitly in valid `YYYY-MM-DD` form. An optional HTTP(S) URL must be an exact, unique quote in the conversation. URL text with ambiguous trailing punctuation is rejected rather than normalized. URLs are validated locally and never fetched.
- The exact canonical preview requires separate explicit approval. Create recomputes the evidence and digest, then performs the append while holding the shared storage mutation lock. Same-body retries return the existing row; altered requests with the same approval ID return 409. A user deletion retains only that random approval UUID in `learning_evidence_agent_approvals.json`; replay after deletion returns 409 and cannot recreate the row. This content-free ledger is included in local backups and grows by one UUID for each deleted agent-created entry.
- Manual LearningEvidence CRUD remains unchanged. The conversation is not stored by Hamartia, no social upload/sync was added, and no provider can write directly.

## Verification

Tests mock both provider adapters; no real provider credentials, network AI calls, or local model execution were used. The deterministic host benchmark fail-fast patches provider-facing `AIService` entry points and checks full stored rows, exact quote offsets, digest and approval fingerprints, same-body replay, altered replay conflict, eight-way concurrent idempotency, and invalid/hypothetical no-write behavior.

Latest local results:

- Focused LearningEvidence, manual CRUD, and backup tests: 37 passed; backup checks cover ledger round-trip and legacy archives without the optional ledger.
- The prior committed head's focused verification was frontend 63/63 and desktop 67/67; the current signed-state head results are recorded below.
- The Playwright browser smoke now includes a LearningEvidence interaction flow: mock ChatGPT tool responses only, EN invalid/incomplete follow-up, EN preview cancel with zero create requests, and TR follow-up/preview/approval with one create whose fields, quote provenance, and digest match the exact host preview. It asserts the fake provider bridge call sequence and blocks/records any page request outside local Vite/API origins; the final assertion requires zero external requests. `node --check frontend/_smoke.cjs` and the frontend unit suite (63/63) pass. The full browser run cannot be completed locally because Chromium lacks `libglib-2.0.so.0`; CI's `npm run test:browser` remains required.
- Generated documentation integrity benchmark passed: 17 pages per language, 818 local links/assets, 108 exact evidence excerpts, zero network or AI calls. The local Playwright docs smoke could not start Chromium because this host lacks `libglib-2.0.so.0`; the CI browser job remains required.
- After adding signed multi-turn state, the full backend suite ran 250 tests: 241 passed and 9 PostgreSQL integration tests skipped because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` is unset. The CI PostgreSQL 17 job remains mandatory. Desktop: 68/68; frontend: 63/63; production build passed with the existing large-chunk warning.
- Signed-state regression tests cover HMAC tampering, one-hour expiry, modified transcript prefix, wrong appended-turn count, one-use replay, host-derived expected field, current-turn-only quote validation, and rejection of caller-provided prior claims. The composed configured-provider test completes three mocked turns and rejects an unrelated old-turn quote without another provider call.
- Host-only benchmark, three measured repeats after one warm-up per size, also measured 100 signed host-state transitions per run. Provider entry points remain fail-fast patched:
  - 24 records: preview/create p50 0.195392 s, p95 0.201626 s, 124.68 records/s; 100 signed transitions p50 0.032928 s, p95 0.033487 s (about 3,037 transitions/s).
  - 64 records: preview/create p50 0.606527 s, p95 0.610975 s, 105.52 records/s; 100 signed transitions p50 0.038013 s, p95 0.038890 s (about 2,571 transitions/s).
  - Eight concurrent retries produced one row in 0.031607 s (24-record trial) and 0.056242 s (64-record trial).
  - Hypothetical writes: 0. Provider tripwire calls: 0.
- Backup tests confirm the approval UUID ledger round-trips and older backups default it empty.

CI checks remain required before PR approval. CI provisions PostgreSQL 17 for the backend integration suite and runs this host-only benchmark with the other backend benchmarks. The desktop ChatGPT adapter is separately covered by mocked Node tests; the host benchmark does not instantiate either provider adapter. Provider execution, model quality/latency/resource behavior, and physical-device verification are intentionally excluded.

## Limitations

This is a narrow deterministic parser for explicitly self-reported evidence, not independent verification of learning or activity. English/Turkish completion checks are conservative patterns and cannot establish factual truth. The preview is a local application safeguard, not a boundary against a malicious process running as the same OS user. Provider operators may retain conversation data under their own policies. No real account/provider call or deployment was performed.
