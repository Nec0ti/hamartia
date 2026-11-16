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
- [x] Extend versioned exact-rational scoring-profile selection and immutable snapshots to completed PracticeSessions, focused-timer completion/idempotency, profile-partitioned topic net/trends, editing, and current/legacy backups; bind host-selected profiles to the Study Agent preview digest without accepting provider selection. Legacy records retain `legacy-yks@1`; practice sessions grant no XP. The non-AI persisted benchmark covers full-row and grouping oracles ([report](reports/2026-11-16-practice-scoring-profiles.md)).
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
- [x] Add a fail-closed, per-request consent gate for question analysis: local-only preview, sanitized destination host/port/scheme/model, exact text/image and auth-category disclosure, one-use immutable snapshots, atomic in-flight question/settings freshness checks, stale-analysis invalidation after prompt-source edits, preview/dispatch/current manual-tag preservation, zero SDK retries, and mocked concurrency/transport/cancel tests ([report](reports/2026-11-16-question-analysis-consent.md)).
- [ ] Run human retrieval/usability tasks with the public key withheld during administration; score answers/citations against the published 90/100 overall, 85% per-locale, and 100% critical-case thresholds, and evaluate fixed-viewport screenshots. This is not a sealed blind gate; no AI/provider scoring ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).
- [x] Verify compatibility of old records/backups, UI, and section-sized missed-question limits for TYT/AYT sessions with subject sections.
- [x] Add a distinct learning-evidence record for a completed suggested activity: user-entered observation/reflection, date, and optional reference link. Keep it separate from binary `ReviewAttempt`, exam net, and XP; do not infer completion or mastery from AI output ([report](reports/2026-11-15-learning-evidence-record.md)).

## P3 — verification on another computer

- [ ] Verify on a separate physical device the OpenAI-compatible endpoint/model settings saved by the app, including the configured-endpoint Study Agent ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).
- [ ] Verify synthetic image transfer to a multimodal endpoint on a separate physical device. Before approving **Review with AI**, inspect the consent dialog's sanitized hostname/effective port, local/remote class, HTTP/HTTPS scheme, model, question/OCR text and image categories, and auth-setting/effective-value categories. The preview stays on the local API; decline/cancel sends no provider request. Approve only when the endpoint operator and transport are trusted. Do not report any real key or value, or run local AI tests/benchmarks here ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).

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
- [x] Implement the conversational Study Agent PracticeSession tool flow for ChatGPT Responses and the configured Chat Completions endpoint. Provider arguments contain only evidence quote hints; the host binds the real transcript/language, verifies claims locally, and permits writes only after exact-preview approval. Keep the tool allowlisted and create-only; provider responses are mocked in tests, and the deterministic benchmark exercises host verification/create with provider entry points guarded by fail-fast tripwires. No real provider/local-AI execution is included in tests or benchmarks. See [the provider tool-loop report](reports/2026-11-16-study-agent-provider-tool-loop.md). Broader record types remain separate backlog work.
- [x] Add the separate LearningEvidence tool flow for ChatGPT Responses and the configured endpoint. Host binds exact quotes to expected student turns, asks bilingual follow-ups for missing/ambiguous evidence, previews the canonical self-reported record, and writes only after explicit approval. Preserve qualified activity wording; never infer date/mastery/whole-task completion or fetch URLs. Exact retries are idempotent, altered approvals conflict, and deleted entries retain only a content-free approval UUID tombstone (also in backups). Mock provider adapters; benchmark deterministic host work with provider tripwires and no model execution ([report](reports/2026-11-16-study-agent-learning-evidence-tool.md)).
- [ ] Complete real SIWC login/inference/cancel/sign-out/revocation/reauthorization on a separate physical user's device. Verify package behavior on consumer Windows 10/11 and Debian as separate P4 checks. Never include account tokens in test data or reports ([manual run template](reports/2026-11-15-external-manual-verification-template.md)).

## P6 — product experience follow-up

- [x] Add a Clock tab for local time, shared practice/Pomodoro/countdown/stopwatch timing, alarms/reminders, and safe backup/restart reconciliation; no streak pressure or exit friction.
- [x] Publish a 17-page EN/TR static wiki for Getting Started, system architecture, study workflows, Cosmos/progression, mistake/review behavior, exam/Maarif scope, OS installs, providers/consent/privacy, backup, Clock, accessibility/language, learning-evidence boundaries, FAQ, troubleshooting, and contribution; validate route and translation parity ([report](reports/2026-11-15-bilingual-wiki-docs.md)).
- [x] Strengthen system-level non-AI benchmarks with persisted end-to-end workloads and explicit correctness checks; keep AI excluded. The quality pass adds full question post-mutation oracles, named untimed persistence fault probes, skewed mixed-size persisted fixtures, multi-process/crash recovery, and loopback HTTP ([report](reports/2026-11-15-system-resilience-benchmark.md)).
- [x] Redesign the public guide as a responsive, keyboard-navigable bilingual wiki; validate navigation, links, mobile width, and page parity without telemetry.
- [x] Add the paired bilingual docs task pack and offline integrity benchmark after the wiki and system benchmark releases. Human retrieval scoring and screenshot evaluation remain open; no AI answer or scoring path is included.

## P7 — private social prototype

- [x] Add the separate opt-in, loopback-only Firebase ID-token boundary with `/social/me` returning only verified UID; keep the desktop/local API untouched ([auth slice](reports/2026-11-16-social-auth-slice.md)).
- [x] Add owner-scoped private profile GET/PATCH over PostgreSQL with per-field private defaults, strict allowlisted fields, and a pure but unmounted public projection. No login UI, public profile route, forum, DM, local study sync, AI context, or hosting is included ([plan and current verification](reports/2026-11-16-social-profile-and-hosting-plan.md)).
- [x] Add an opt-in bilingual Google sign-in/private-profile UI prototype with system-browser OAuth on Electron, browser-dev Firebase popup, fixed transport, and an unchecked pre-auth acknowledgement gate. The current builds remain disabled without provider/API configuration and a reviewed agreement version; no live provider or server-side consent receipt is included ([implementation and offline benchmark report](reports/2026-11-16-social-signin-onboarding.md)).
- [x] Add a private moderated study forum on the separate PostgreSQL social service: Firebase-verified author identity, server-configured moderator UIDs, pending-only submission, authenticated approved-only reads, self-moderation rejection, one-way concurrent decisions, and bilingual signed-in UI. Migration is additive and rollback preserves rows; no public reads, DMs, real provider credentials, or deployment ([implementation and benchmark report](reports/2026-11-16-moderated-study-forum.md)).
- [ ] Before enabling sign-in or any public launch, approve versioned User Agreement/privacy text and complete legal/privacy, provider/API-host, Cloudflare/network, security, and physical-host readiness gates in the reports. The UI acknowledgement can be bypassed by custom clients; do not treat the prototype or CI as legal protection or gate completion.

## Next small task

The moderated forum slice is complete and remains private/opt-in; authenticated reads include only approved posts, and DMs remain deferred. Study-data sync is a separate approved slice. Before enabling sign-in, collecting real-user data, or any public deployment, complete the agreement/legal/privacy, provider/API-host, Cloudflare/network, security, and physical-host gates in [the social planning report](reports/2026-11-16-social-profile-and-hosting-plan.md). Separately complete the outstanding real SIWC, consumer-device package, configured-endpoint, and human docs retrieval/usability checks. Keep real provider execution and quality outside CI and benchmarks.
