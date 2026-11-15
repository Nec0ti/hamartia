# Backlog

## P0 — data integrity

- [x] Reading a list must not silently present malformed/partial JSON as empty data.
- [x] Labeling, saving analysis results, and deletion must use atomic read-modify-write.
- [x] Test that no records are lost during competing updates.
- [x] A local model/endpoint error must not be saved as a fake Council diagnosis or error label; show the error and preserve records.
- [x] The Settings API must not leak a stored API key in responses; saving an empty value must preserve it, and explicit clearing must be supported.

## P1 — student workflow

- [x] Enter practice exams, preserve history, save missed-question images locally, and label them.
- [x] Connect the home page and My Mistakes tab to real flows.
- [x] Derive deterministic study priorities from subject/topic error patterns.
- [x] Mark a missed question as reviewed, update the plan, and allow undo.
- [x] Store correct/incorrect attempts with the user's explicit local calendar day and calculate review intervals locally; retain UTC-date fallback for legacy records and clients that omit the optional day.
- [x] Remove the image requirement and provide text-based missed-question capture with a visible entry form.
- [x] Store TYT/AYT/branch exam types, filter by type, and separate totals.
- [x] Edit and confirmed-delete existing records throughout exam history.
- [x] Save a full TYT/AYT practice exam by subject in one session; count total net and XP once, preserving subject trends and missed-question context.
- [x] Turn the Cosmos placeholder into a safe, local, AI-free progress flow.
- [x] Close the legacy Cosmos attack/reward route, whose rules are unclear, with 410; safely write node/sector mutations under one document lock.
- [x] Edit text/subject/topic in missed-question records; use a deletion flow that preserves images and does not delete files outside uploads.
- [x] Show different questions attempted today and all correct/incorrect answers in the study plan.
- [x] When capturing a missed question from an exam, store question number, solve order, and time spent; show the order and time distributions of saved missed questions.
- [x] Record completed topic practice sets separately; derive net, answered-question accuracy, and topic trends only from these sets.
- [x] Start a focused study session from a priority topic; track time and correct/incorrect/blank counts, then convert it to the existing set record when finished.
- [x] Show net and accuracy trends as charts for topic practice sets; provide edit/delete access to sets older than the last six records.
- [x] Start the local API and frontend with one command; check readiness and port conflicts.

## P2 — verification and hardening

- [x] Non-AI backend tests for formulas, boundary validation, records, and the image route.
- [x] Storage and question workflow benchmarks; frontend test/build baseline.
- [x] End-to-end smoke test of the real browser flow and a basic accessibility check.
- [x] Audit frontend dependencies online against current advisories.
- [x] Verify the Vite security patch and frontend dependency installation/build.
- [x] Verify behavior for malformed JSON and the legacy CouncilAnalysis format.
- [x] Download a ZIP backup without the API key from Settings and validate restore while the app is closed.
- [x] Capture backups as one point-in-time snapshot during live writes; keep uploaded question images inside the configured data directory.
- [x] Preserve the current data directory as a snapshot before restore and protect directory swap with a process lock.
- [x] Benchmark backup creation, validation, and restore using representative data, without AI.
- [x] Replace single-shot benchmark probes with seeded persisted mixed workloads, correctness oracles, repeated percentiles, and machine metadata; keep sequential JSON append labeled as stress-only.
- [x] Compare complete benchmark outputs against independent expected values; add boundary/skew fixtures, corruption and restore-safety cases, and deterministic wrong-result probes outside timed sections.
- [ ] Extend storage failure and concurrency coverage with multi-process writers, process termination during atomic replacement, and restart/recovery reconciliation. Keep these correctness experiments separate from throughput timing.
- [ ] Add bounded loopback HTTP API benchmarks that measure serialized request/response and concurrent client paths separately from direct-function microbenchmarks; guarantee no external or AI endpoint request.
- [ ] Add a blind bilingual documentation retrieval benchmark with versioned EN/TR tasks, citation/answer scoring, stale and broken link fixtures, and fixed-viewport browser/screenshot checks. Do not use AI to answer or score tasks.
- [x] Verify compatibility of old records/backups, UI, and section-sized missed-question limits for TYT/AYT sessions with subject sections.
- [ ] Add a distinct learning-evidence record for a completed suggested activity: user-entered observation/reflection, date, and optional reference link. Keep it separate from binary `ReviewAttempt`, exam net, and XP; do not infer completion or mastery from AI output.

## P3 — verification on another computer

- [ ] Verify on a separate computer the OpenAI-compatible endpoint/model settings saved by the app, including the configured-endpoint Study Agent.
- [ ] Verify image transfer to a multimodal endpoint with a real model; do not run local AI tests or benchmarks in this repository.

## P4 — product language and delivery

- [x] Provide English (default) and Turkish application UI, with a persistent language selector.
- [x] Publish a user-focused English/Turkish guide with GitHub Pages; keep planning notes and internal reports off the public site.
- [x] Package for Windows 10/11, Debian (`.deb`), and AppImage; store user data in the platform's per-user application data directory. NSIS and `.deb` install, app launch, and cleanup checks passed on Windows Server 2022 and Ubuntu 22.04; a separate frozen-backend smoke verified persistence on both. Consumer Windows 10/11 and separate Debian desktop installs remain manual checks.
- [x] Publish a GitHub Release after each merged PR with a bilingual release note and sequential themed code (`ARETE-001`, `ARETE-002`, ...). PR #5 produced ARETE-001 and PR #8 produced ARETE-004 automatically; later sequential allocations can be verified by subsequent merged PRs.
- [x] Keep source code, internal Markdown, PRs, and other GitHub prose in English; keep `RELEASES.md` bilingual.

## P5 — study agent

- [x] Add explicit-consent Sign in with ChatGPT subscription usage as the default Study Agent provider; add the configured OpenAI-compatible endpoint as an explicit optional provider. Question analysis remains separate.
- [x] Show per-request endpoint consent and trust warnings for the configured Study Agent; keep the saved API key in the backend and disclose when it is sent for authentication.
- [x] Test the OAuth and API integration with mocks; exclude real ChatGPT/local model calls from CI and benchmarks.
- [x] Verify native packaged Electron `safeStorage` behavior on Ubuntu 22.04 (GNOME Secret Service accepted; `basic_text` rejected) and Windows Server 2022 (native Windows protected storage round-trip) in CI; see [the 2026-11-15 verification report](reports/2026-11-15-chatgpt-plan-study-agent.md).
- [ ] Complete a real SIWC login/inference/sign-out on a user's desktop; verify package behavior on consumer Windows 10/11 and a separate Debian desktop. Never include account tokens in test data or reports.

## Next small task

Next: complete real SIWC account checks and consumer-machine package checks on supported desktop platforms, then manually verify the configured Study Agent endpoint on another computer. Keep all real provider execution and quality outside CI and benchmarks. Verify subsequent ARETE numbering on a later merged PR.
