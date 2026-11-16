# Study Agent single-subject branch-exam capture

Date: 2026-11-16
Scope: a bilingual, local-first branch-exam entry flow using the existing ChatGPT Responses and configured OpenAI-compatible provider choices. This is a bounded data-entry slice, not a claim of broader launch, legal, hosting, or physical-device readiness.

## Behavior and trust boundary

- The workflow creates one `branch` exam for one subject. It leaves manual exam CRUD and sectioned TYT/AYT exam behavior unchanged.
- Provider tools accept only one `{field, quote}` hint at a time. The host owns field order, transcript state, locale, parsing, scoring-profile choice, derived net/XP, source quotes, canonical preview, and write authorization. The provider cannot select exam type/profile or submit parsed values, counts, date, duration, score, IDs, or write commands.
- The host requires explicit current-turn answers for date (`YYYY-MM-DD`), subject, correct/incorrect/blank nonnegative integer counts, whole minutes, and additional seconds. No date or duration is defaulted. Missing, invalid, uncertain, or stale evidence cannot create a preview; each follow-up is generated in English or Turkish by the host.
- A short-lived, one-use HMAC token binds prior host-verified quote claims to locale, selected profile version, transcript prefix, and the next appended turn. Tokens are canonical-base64url/HMAC checked and replay protected. They contain no record body and are not logged or persisted. Tokens are not principal-bound; this workflow remains scoped to the existing single-user local app. Remote/multi-user use would require binding state to a server-verified principal first.
- The explicit preview shows each exact source quote, selected immutable scoring-profile snapshot, and host-computed net/XP. Save is a separate approval request that recomputes fields, provenance, profile, and derived values, then checks and appends atomically under the storage lock. Exact same-body retry returns the existing row. For schema-valid requests, a previously consumed approval UUID returns 409 before altered-body semantic validation, including when its altered preview would otherwise fail recomputation. Schema-invalid request shapes are rejected with generic 422 by request validation before approval lookup. If a schema-valid but semantically malformed request wins the lock before any request has consumed the ID, it returns generic 422 without consuming the ID; a later valid request may then create the row. Validation, recomputation, and append are serialized to make this ordering deterministic. Concurrent identical approvals create one row. Deletion retains only the random approval UUID in an optional backup-compatible ledger so replay cannot recreate the removed record.
- Browser UI and desktop IPC send the host-selected profile only to local verification/create paths. The provider tool contract contains only the expected field and quote; no provider receives a scoring-profile ID/version.
- No real provider credentials, real provider/network AI calls, local model execution, model quality/latency/resource measurement, or deployment was used. The feature is not enabled against public social services.

## Verification

- Full backend discovery after this follow-up: 284 tests, 275 passed and 9 skipped. The skipped tests are PostgreSQL integration cases in `test_social_profile.py` and `test_social_forum.py`, because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` is unset locally; CI's PostgreSQL 17 service remains mandatory. The focused branch-exam suite now has a deterministic malformed-vs-valid same-ID race test: it verifies semantic recomputation holds the mutation lock, the malformed request returns 422 without a write, then the waiting valid request creates one row. Other focused coverage includes exact field order, strict numeric/date parsing, profile binding, token replay/tampering, no-write invalid/incomplete cases, 9-claim request rejection, consumed altered approval 409, concurrent one-row create, deletion tombstone replay, Turkish create locale, and a legacy backup archive with the optional ledger absent.
- Configured-provider adapter and `/study-agent/local` composition tests use mocks only. Desktop ChatGPT tool-call and IPC adapter tests use mock Responses and local API endpoints; no provider is contacted.
- Frontend unit suite: 65/65 passed. Desktop mock suite: 71/71 passed. Vite production build passed with the existing large-chunk-size warning.
- The Playwright browser smoke passed under the Nix Chromium executable with a mocked desktop bridge and only local Vite/API origins. English covers all seven follow-ups and cancel with zero create requests. Turkish approves once and checks that saved fields, evidence, selected profile, locale, net, and XP exactly match the preview. It asserts the mock provider bridge log contains only field, quote, and locale, and that the external-request tripwire records zero external origins. The run reports `ai_included: false`; synthetic created rows and their content-free deletion ledger are removed with the disposable data directory.
- The documentation browser smoke passed 34 pages with reciprocal locale links, section parity, internal links, a 390px viewport, and keyboard skip navigation. Browser runs use Nix Chromium because Playwright's cached Chromium requires `libglib-2.0.so.0`, which is not available to the default local browser.
- Public EN/TR Study Agent and Privacy/Consent pages now document the branch-exam transcript/expected-field provider boundary, host-only profile and record identifiers, host-computed net/XP, explicit approval, and the separation from sectioned/manual exam entry. The docs integrity smoke checks these details in all four rendered pages.
- A deterministic host-only benchmark patches all provider-facing `AIService` methods to fail immediately if called. It validates full persisted rows, exact quote provenance, canonical preview digest, independently computed legacy net/XP, idempotent same-body replay, altered 409, invalid no-preview/no-write, and eight concurrent approvals producing one row. It also times 100 HMAC state transitions per trial. The benchmark emits `ai_included: false` and reports zero provider tripwire calls.

### Host-only benchmark results

Command: `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_study_agent_exam.py --repeats 3`

One warm-up trial is excluded. These are host parsing/storage timings, not provider or model measurements.

| Records | Preview + approved create p50 | p95 | Final-trial throughput | 100 state transitions p50 | p95 | Concurrent 8-request create |
|---:|---:|---:|---:|---:|---:|---:|
| 24 | 0.421088 s | 0.496081 s | 58.14 records/s | 0.048690 s | 0.080001 s | 0.037489 s; 1 row |
| 64 | 1.625194 s | 1.671928 s | 38.28 records/s | 0.100705 s | 0.106107 s | 0.067824 s; 1 row |

Both sizes reported 0 invalid-preview writes, 0 provider tripwire calls, one same-body replay, one altered replay conflict, and an independent-oracle corruption probe detected as expected.

## Checks and CI

CI must run the backend suite with PostgreSQL 17, this host-only benchmark, frontend/browser tests, desktop adapter tests, and Linux/Windows package checks before merge. No CI result or release is implied by this report.

## Limitations

This parser verifies exact student-provided values and deterministic constraints; it cannot establish that a student’s statements are factually correct. Net and XP use the selected host-owned scoring profile and existing score rules. Preview/approval is an application safeguard, not a boundary against a malicious process running as the same OS user. No real-provider, physical-device, legal, or hosting readiness conclusion is made.
