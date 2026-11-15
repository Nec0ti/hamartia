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
- [x] Add versioned, editable exact-rational scoring profiles for exam records; snapshot rules on each exam, isolate score trends by profile/version, preserve legacy YKS score/backup behavior, and keep XP based on the same raw-count activity formula ([report](reports/2026-11-15-exam-scoring-profiles.md)).
- [ ] Extend versioned scoring-profile selection and immutable snapshots to completed PracticeSessions, focused-timer completion/idempotency, topic net/trends, editing, and backups. Until implemented, these practice-set nets remain on the legacy YKS quarter-penalty formula ([report](reports/2026-11-15-exam-scoring-profiles.md)).
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
- [x] Compare complete benchmark outputs against independent expected values; add boundary/skew fixtures, corruption and restore-safety cases, and deterministic wrong-result probes outside timed sections ([report](reports/2026-11-15-benchmark-oracle-hardening.md)).
- [x] Add a deterministic Clock benchmark with seeded timer-oracle scenarios, 128-alarm/DST/missed-event controls, separate persisted API timing, failed-write checks, and backup/restore safety ([report](reports/2026-11-15-student-clock.md)); no AI included.
- [x] Extend storage failure and concurrency coverage with multi-process writers, process termination during atomic replacement, and restart/recovery reconciliation. Keep these correctness experiments separate from throughput timing ([report](reports/2026-11-15-system-resilience-benchmark.md)).
- [x] Add bounded loopback HTTP API benchmarks that measure serialized request/response and concurrent client paths separately from direct-function microbenchmarks; guarantee no external or AI endpoint request ([report](reports/2026-11-15-system-resilience-benchmark.md)).
- [x] Add a versioned paired EN/TR documentation task workbook, separate human answer rubrics with page/anchor evidence, synthetic stale/broken-link decoys, and an offline rendered-route/link/evidence integrity checker; task and key files are public and inspectable, so this is not a cryptographically sealed blind gate ([report](reports/2026-11-15-docs-retrieval-benchmark.md)).
- [ ] Run human retrieval/usability tasks with the public key withheld during administration; score answers/citations against the published 90/100 overall, 85% per-locale, and 100% critical-case thresholds, and evaluate fixed-viewport screenshots. This is not a sealed blind gate; no AI/provider scoring ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).
- [x] Verify compatibility of old records/backups, UI, and section-sized missed-question limits for TYT/AYT sessions with subject sections.
- [x] Add a distinct learning-evidence record for a completed suggested activity: user-entered observation/reflection, date, and optional reference link. Keep it separate from binary `ReviewAttempt`, exam net, and XP; do not infer completion or mastery from AI output ([report](reports/2026-11-15-learning-evidence-record.md)).

## P3 — verification on another computer

- [ ] Verify on a separate physical device the OpenAI-compatible endpoint/model settings saved by the app, including the configured-endpoint Study Agent ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).
- [ ] Verify synthetic image transfer to a multimodal endpoint on a separate physical device. First inspect the host, HTTP/HTTPS transport, model, and configured auth-key state in Settings; question text/OCR, image, and configured key/placeholder may be sent after manually initiating `Review with Local AI`. This flow has no separate per-request consent gate (unlike Study Agent, whose consent excludes saved question images); mark BLOCKED if remote, plaintext, or key transmission is unacceptable. Do not report any real key or value, or run local AI tests/benchmarks here ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).

## P4 — product language and delivery

- [x] Provide English (default) and Turkish application UI, with a persistent language selector.
- [x] Publish a user-focused English/Turkish guide with GitHub Pages; keep planning notes and internal reports off the public site.
- [x] Build Windows 10/11-targeted, Debian (`.deb`), and AppImage packages with app data scoped to each platform's per-user directory. CI package-install/launch/cleanup checks passed on Windows Server 2022 and Ubuntu 22.04; separate frozen-backend smokes verified persistence on those CI environments.
- [ ] Manually verify install, launch, and synthetic-record persistence on separate physical consumer devices running Windows 10 and Windows 11 individually, plus a separate physical Debian desktop for `.deb` install and AppImage launch/persistence; CI runner results do not complete these checks ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).
- [x] Publish a GitHub Release after each merged PR with a bilingual release note and sequential themed code (`ARETE-001`, `ARETE-002`, ...). PR #5 produced ARETE-001 and PR #8 produced ARETE-004 automatically; later sequential allocations can be verified by subsequent merged PRs.
- [x] Keep source code, internal Markdown, PRs, and other GitHub prose in English; keep `RELEASES.md` bilingual.

## P5 — study agent

- [x] Add explicit-consent Sign in with ChatGPT subscription usage as the default Study Agent provider; add the configured OpenAI-compatible endpoint as an explicit optional provider. Question analysis remains separate.
- [x] Show per-request endpoint consent and trust warnings for the configured Study Agent; keep the saved API key in the backend and disclose when it is sent for authentication.
- [x] Test the OAuth and API integration with mocks; exclude real ChatGPT/local model calls from CI and benchmarks.
- [x] Verify native packaged Electron `safeStorage` behavior on Ubuntu 22.04 (GNOME Secret Service accepted; `basic_text` rejected) and Windows Server 2022 (native Windows protected storage round-trip) in CI; see [the 2026-11-15 verification report](reports/2026-11-15-chatgpt-plan-study-agent.md).
- [ ] Complete real SIWC login/inference/cancel/sign-out/revocation/reauthorization on a separate physical user's device. Verify package behavior on consumer Windows 10/11 and Debian as separate P4 checks. Never include account tokens in test data or reports ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).

## P6 — product experience follow-up

- [x] Add a Clock tab for local time, shared practice/Pomodoro/countdown/stopwatch timing, alarms/reminders, and safe backup/restart reconciliation; no streak pressure or exit friction.
- [x] Publish a 17-page EN/TR static wiki for Getting Started, system architecture, study workflows, Cosmos/progression, mistake/review behavior, exam/Maarif scope, OS installs, providers/consent/privacy, backup, Clock, accessibility/language, learning-evidence boundaries, FAQ, troubleshooting, and contribution; validate route and translation parity ([report](reports/2026-11-15-bilingual-wiki-docs.md)).
- [x] Strengthen system-level non-AI benchmarks with persisted end-to-end workloads and explicit correctness checks; keep AI excluded. The quality pass adds full question post-mutation oracles, named untimed persistence fault probes, skewed mixed-size persisted fixtures, multi-process/crash recovery, and loopback HTTP ([report](reports/2026-11-15-system-resilience-benchmark.md)).
- [x] Redesign the public guide as a responsive, keyboard-navigable bilingual wiki; validate navigation, links, mobile width, and page parity without telemetry.
- [x] Add the paired bilingual docs task pack and offline integrity benchmark after the wiki and system benchmark releases. Human retrieval scoring and screenshot evaluation remain open; no AI answer or scoring path is included.

## Next small task

Next: complete the P5 real SIWC and consumer-device package checks, then manually verify the configured Study Agent endpoint on a separate physical device. Keep all real provider execution and quality outside CI and benchmarks. Clock and wiki docs are implemented; continue P6 with stronger system benchmarks, then administer the public human docs retrieval/usability tasks with the answer key withheld during sessions, noting this is not a sealed blind test. Verify subsequent ARETE numbering on a later merged PR.
