# Study Agent sectioned TYT/AYT exam capture

Date: 2026-11-16
Scope: a separate bilingual conversational flow to capture one sectioned TYT or AYT exam. Manual exam entry and the single-subject branch flow remain separate. No canonical official subject roster is introduced or claimed.

## Behavior and trust boundary

- The host explicitly asks for exam type (TYT or AYT), exact date, duration minutes and seconds, section count, and each section's subject and correct/incorrect/blank counts. It accepts only one to six student-specified sections. Because the existing Study Agent turn cap is 30 and the six-section path uses 29 field turns, the UI and documentation show the 1–6 ceiling. There are no default values, inferred fields, or assumed official subject list.
- The selected immutable scoring profile is chosen and snapshotted locally before provider dispatch. Profile ID/version/rules are not conversational facts and are not sent to the provider. The provider can return only an exact quote hint for the host's current expected field; the host controls field order, validation, section order, totals, net/XP, digest, preview, and approval.
- The selected provider (ChatGPT subscription or configured OpenAI-compatible endpoint, which may be remote) receives the current student transcript only after explicit per-request consent. No real provider or local-model execution was used in tests, smoke runs, or benchmarks. Transcript and signed continuation state are not persisted. Continuation state is short-lived, one-use, and scoped to the sectioned-exam flow, transcript, language, and selected profile.
- A canonical preview exposes every section and exact quote, aggregate totals, selected profile snapshot, net, and XP. A separate approval writes one row. Storage locking, exact retry idempotency, changed-body conflicts, concurrent create convergence, UUID-only deletion tombstones, and tombstone backup/restore are host-owned. Cancellation and invalid or ambiguous evidence write nothing.
- The six-section cap does not assert that any entered section list matches an official TYT/AYT roster. The parser checks the student's explicit claims and basic field constraints; it cannot prove the statements are factually true.

## Verification

- Focused sectioned-exam backend suite: 7/7 passed after fixing and pinning the `section_count` follow-up to preserve the visible `(1-6)` limit in both EN and TR.
- Full backend discovery: 293 tests, passed; 9 PostgreSQL integration tests skipped because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` is unset. No database integration result is implied.
- Desktop adapter/IPC mock tests: 32/32 passed; full desktop suite: 73/73 passed. Provider adapters are mocked.
- Frontend unit suite: 66/66 passed. Vite production build passed; existing large-chunk warning remains.
- Playwright browser smoke ran with Nix Chromium and local Vite/API origins. English captured one section then cancelled; the create route was never called and no exam row was written. Turkish captured one section, approved once, and the complete persisted row exactly matched preview sections, aggregate counts, selected profile, net and XP. The smoke verifies the 1–6 hint in both locales, provider calls contain only the current field/quote hint plus locale, deleted approval ledger rows contain no transcript, and the external browser request tripwire is zero. Output declares `ai_included: false`.
- Docs browser smoke passed 34 pages, paired locale links, matching section anchors, local links/assets, 390px layout, and keyboard skip link. Docs integrity passed with 34 pages, 17 routes per locale, 818 local links/assets, and no errors. Both tools are offline and do not contact providers.

## Persisted host-only benchmark

Command:

```sh
PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_study_agent_sectioned_exam.py --repeats 3 --json-output reports/2026-11-16-study-agent-sectioned-exam-benchmark.json
```

One warm-up is excluded. Independent oracles cover ordered section contents, aggregate totals, selected profile snapshot, rational net and XP, preview digest, exact persisted full row, cancel/no-write, same-body retry, altered replay conflict, and eight concurrent requests converging on one row. Five wrong-result probes (section roster, aggregates, profile, net, XP) are run outside timed sections. Every `AIService` provider entry point is fail-fast patched. The replay cache is cleared only between fresh trials after the benchmark proves there are no live continuation tokens; each trial asserts its used-token cache remains under the fixed 4096-entry capacity. All runs reported zero provider calls and `ai_included: false`.

| Records | Sections checked | Preview + approved create p50 | p95 | Final-trial throughput | Used cache / capacity | Concurrent approvals |
|---:|---:|---:|---:|---:|---:|---:|
| 24 | 89 | 0.381327 s | 0.391621 s | 61.28 records/s | 456 / 4096 | 8 requests, 1 row |
| 64 | 225 | 1.345648 s | 1.346241 s | 47.90 records/s | 1160 / 4096 | 8 requests, 1 row |

The JSON result is in [the benchmark report](2026-11-16-study-agent-sectioned-exam-benchmark.json), and the source-generated public EN/TR Study Agent and Privacy/Consent content is verified in [the docs integrity result](2026-11-16-study-agent-sectioned-exam-docs.json).

## Limitations

- The browser/provider adapters are mocked. There are no ChatGPT calls, configured endpoint calls, local AI inference runs, model-quality claims, or AI performance measurements.
- The benchmark measures only host parsing, validation, preview, scoring, persistence, and concurrency on this development machine. It is not an end-to-end provider benchmark.
- Nine PostgreSQL social integration tests were skipped without the configured test database. Human docs usability and physical-device/package checks remain separate work.
- Desktop `npm run pack:dir` completed the UI build but could not build the backend/package because the system Python has no `PyInstaller` module. The desktop test suite and frontend production build passed; a packaged desktop artifact was not produced.
- Preview/approval and local storage locking protect application flows, not against a malicious process running as the same OS user.
