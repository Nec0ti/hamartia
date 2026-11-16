# Study Agent text-only missed-question capture

Date: 2026-11-16
Scope: a local-first, text-only missed-question capture mode using the existing ChatGPT Responses and configured OpenAI-compatible provider options. This is a bounded correctness slice, not a claim of broader launch, legal, or hosting readiness.

## Behavior and boundaries

- The initial prompt asks the student to paste the complete problem as one message. Subject and topic are optional and are requested in separate localized turns; the student can use the localized skip option. Repeating the same skip answer for both optional fields is valid because each signed continuation binds the claim to its newly appended, host-expected turn.
- Provider tools accept only `{field, quote}` evidence hints. The host owns language, transcript ordering, expected field, source offsets, value parsing, preview digest, and write authorization. A quote must be an exact entire student message in the field's expected turn. Non-skip repeated quotes, stale-turn quotes, out-of-order hints, hypothetical/negated/future question statements, incomplete drafts, and invalid input cannot produce an approvable preview.
- The final preview contains only exact problem text, optional subject/topic, and their source quotes. It does not add an image, URL, analysis, mistake tag, curriculum mapping, user ID, or provider-proposed record value. The student must separately approve the exact preview before `/questions/agent-create` writes a record. Cancel sends no create request.
- Create recomputes the fields, evidence, and preview digest, then performs an atomic append. Exact same-body retries return one record; changed replay with the same approval UUID returns 409. A deleted AI-created question retains only its random approval UUID in the content-free tombstone ledger, so replay cannot recreate deleted data. Manual multipart Question CRUD remains unchanged.
- Multi-turn continuation uses a short-lived, one-use HMAC state token containing host-verified claims, locale, message count, and transcript-prefix digest. The per-process key invalidates outstanding tokens on restart. Tampering, expiry, changed prefixes, wrong turn counts, and replay fail closed. The token is not bound to a user principal and is safe only within the existing single-user local app; remote or multi-user use requires server-verified principal binding first.
- Both provider adapters are tested with mocks. No real provider credentials, network AI calls, local model execution, image upload, URL fetch, or social upload/sync was used.

## Verification

- Focused Question capture backend/API tests: 14 passed. These include exact quote order, repeated optional skip on consecutive turns, stale old-turn rejection (including composed configured-provider flow), signed token tampering/expiry/prefix/replay, invalid no-preview/no-write, exact and altered approval replay, concurrency, deletion tombstone replay, and unchanged multipart manual creation. Full backend suite: 268 tests, 259 passed, 9 PostgreSQL integration tests skipped locally because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` is unset; CI provisions PostgreSQL 17.
- Frontend unit suite: 64/64 passed. Full desktop mock suite: 69/69 passed.
- Local Playwright smoke passed under Nix Chromium with a fake provider bridge and a network tripwire allowing only local Vite/API origins. EN flow reviewed the preview then cancelled with zero `/questions/agent-create` calls; TR flow used `atla` for both optional fields, checked the exact preview, then approved exactly one create. The fixture also checks the fake provider call log and creates/deletes its synthetic row in `try/finally`. The smoke output reports `ai_included: false`; no external request occurred. The isolated API/Vite/browser processes exited and temporary browser/data directories were cleaned.
- Vite production build passed with the existing large-chunk warning. `git diff --check` passed.
- Host-only benchmark `benchmark_study_agent_question.py --repeats 3` passed correctness checks and reports `ai_included: false`, 0 provider tripwire calls, 0 invalid/hypothetical writes, 0 post-delete replay writes, and 8 concurrent same-approval requests producing one record. Three runs reported:

| Synthetic records | Preview + approved create p50 | p95 | Final-trial duration / throughput | 100 signed repeated-skip turns |
|---:|---:|---:|---:|---:|
| 24 | 0.146005 s | 0.188741 s | 0.188741 s / 127.16 records/s | 0.071220 s / 1,404.10 transitions/s |
| 64 | 0.402138 s | 0.451477 s | 0.343756 s / 186.18 records/s | 0.074208 s / 1,347.57 transitions/s |

These timings measure deterministic host validation/storage only; they are not model execution, quality, latency, or resource measurements.

## CI and remaining checks

The benchmark is wired into backend CI. The local docs smoke passed for 34 rendered pages, reciprocal locale links, section parity, internal links, 390px layout, and keyboard skip link. The offline docs-integrity benchmark passed with 17 routes per language, 818 local links/assets, and zero errors/network/AI. CI's PostgreSQL 17 test job, frontend/browser smoke, desktop Linux/Windows package checks, and current-head independent review remain required before PR merge. This work makes no real-provider or physical-device claim and does not change the separate SIWC manual checklist.
