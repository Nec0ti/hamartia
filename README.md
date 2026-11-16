# Hamartia

![Hamartia review path mark](assets/brand/hamartia-mark.svg)

A local-first study tool for learners across curricula: record missed questions, spot patterns in mistakes, and turn them into targeted practice and review. Hamartia grew from Turkish mock-exam workflows, but is intended to be useful across countries and exam systems. Current built-in full-mock entry supports TYT/AYT; single-subject exams and topic practice are generic. Subject/topic labels and curriculum references are free-form. Records keep an immutable scoring-profile snapshot: older and profile-omitting records retain the legacy YKS rule, while users can choose or define versioned exact-rational profiles for new exams and practice sessions. User-entered profiles and curriculum references do not establish official exam or curriculum alignment. The interface supports English and Turkish. Hamartia is original software licensed under MIT; contributions and forks are welcome. It does not use content from external platforms.

## Documentation

The English and Turkish user guide is published on [GitHub Pages](https://nec0ti.github.io/hamartia/).

## Run locally

Python 3.12 and Node.js 22 are required. For the initial setup:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci
```

For daily use, open one terminal at the repository root:

```sh
.venv/bin/python scripts/dev.py
```

The launcher checks that the API is ready and stops both processes together; press Ctrl+C to stop it. The UI is at `http://127.0.0.1:5173`, and the API documentation is at `http://127.0.0.1:8000/docs`. If another app is using 5173, choose an available port with `HAMARTIA_FRONTEND_PORT=5174 .venv/bin/python scripts/dev.py`.

Exams, missed questions, timers, reminders, and settings are stored under `backend/data/`. Question images are in that directory's `uploads/` folder. You can download a ZIP backup from Settings. The backup does not contain the personal API key; restoring preserves the key on the current computer.

A full TYT/AYT practice exam is saved as one session, with correct/incorrect/blank counts entered per subject; total net and XP are calculated once. History and trend subject filters show the selected section's net score. When adding a missed question from a section, the question number and solve order are limited by that section's question count. Branch exams remain single-subject.

## Clock

The Clock tab provides a local date/time display, configurable Pomodoro work and break lengths (25/5 minutes by default), countdown, stopwatch with laps, and one-off or weekday reminders. Study Plan focused practice uses this same persisted timer, so only one timer can run at a time. Running state is derived from timestamps and reconciled after restart; older localStorage practice drafts are migrated only after a successful backend save. Clock state is included in backups. Restoring a backup disables reminders and pauses timers while preserving their remaining or elapsed time.

Notifications are optional and require an explicit in-app permission action. Hamartia checks timers and alarms while the app is open and the device is awake, including while another tab is selected; it cannot wake a sleeping device or notify after the app closes. Operating system settings can suppress delivery, so overdue timers and reminders remain visible in the Clock tab. Each due alarm can produce one event; missed recurring occurrences are skipped. This does not replace an operating-system alarm service.

Close the app before restoring, and run this from the repository root:

```sh
.venv/bin/python scripts/restore_backup.py hamartia-backup.zip
```

Restore validates the full archive and record schemas, then preserves the current `backend/data/` directory as `backend/data.before-restore-.../`. On Windows, use `.venv\\Scripts\\python.exe`. The operation is safely rejected while Hamartia is running.

## Configured AI endpoint

Question-image analysis and the optional Study Agent can use the OpenAI-compatible endpoint configured in Settings. Enter its URL, model name, and optional key. The default URL is `http://localhost:4000/v1`; other hosts are allowed, so the endpoint may be a remote service and is not guaranteed to be local or network-isolated. The Study Agent shows the exact destination, warns for every non-loopback host, and separately warns about unencrypted HTTP. Only use an endpoint you trust. The connected model must accept image content for question-image analysis. The API key is not shown in API responses; leaving the field empty preserves it, and you can remove it with the explicit option in Settings.

Before question analysis, Hamartia makes a local-only preview and asks for approval on every request. The dialog shows the sanitized endpoint host and effective port, whether it is local or remote, HTTP or HTTPS, the model, the saved question/OCR text and image filename fields, whether image bytes are included, and the authentication-value category. It never displays the key. Question/OCR text is limited to 64 KiB of UTF-8 data and saved images to 10 MiB. Approving sends one request to that configured endpoint; canceling sends no provider request. A blank key setting currently sends the SDK's placeholder value. Failed requests are not automatically retried. The endpoint may be remote, so approve only an operator and transport you trust.

For manual verification on another computer, save the server address/model/key; then choose **Review with AI** for a synthetic text question and review the consent dialog before approving. Repeat with a synthetic image only if the destination is trusted. On success, the Council result is saved. An endpoint/model error produces a visible error and leaves the current question label/analysis unchanged. Real model execution remains outside automated tests and benchmarks.

## ChatGPT Study Agent

The packaged desktop app defaults to **ChatGPT subscription** for the Study Agent and offers the configured OpenAI-compatible endpoint as an optional second provider. Choosing a provider is explicit; Hamartia never switches providers after an error. ChatGPT uses OpenAI's open-source Sign in with ChatGPT plan-use flow. Signing in and allowing plan use are user-controlled; only a token response that grants `chatgpt.tokens.use.direct` and `resource.invoke` enables requests. Availability and plan limits depend on the ChatGPT account.

The Study Agent is a general study assistant, not an official or verified curriculum-alignment system. You can attach a generic user-entered curriculum reference to a missed question: framework, source/version, grade/year, unit/theme, a short outcome note or paraphrase, process component, and an optional source URL. The existing subject field supplies course/subject. Hamartia does not automatically fetch or verify the URL; you can open it yourself. Hamartia does not import or bundle MEB curriculum text. If you provide a reference, the Study Agent can relate mistake patterns to it cautiously and suggest a next activity plus a separate task with observable evidence criteria. It does not infer mastery from one answer or record task completion; learning-evidence records remain separate from review attempts, exam scores, and XP. MEB describes the Maarif Model as a phased teaching-program framework with learning outcomes and varied formative evidence. The 2026 [YKS schedule](https://www.osym.gov.tr/2026yks-basvurularin-alinmasi) lists TYT, AYT, and YDT; MEB separately published a [2026 central-exam guide for secondary-school placement](https://www.meb.gov.tr/meb_iys_dosyalar/2026_04/03170012_LGS_Basvuru_ve_Uygulama_Kilavuzu_2026_.pdf). These exam systems remain distinct from the curriculum model. Hamartia's current built-in full-mock formats are TYT/AYT; single-subject exams support user-selected scoring profiles, including custom exact-rational rules. The built-in legacy YKS profile is one available scoring rule, not a universal standard. See the official [Maarif assessment overview](https://tymm.meb.gov.tr/olcme-degerlendirme), [common text](https://tymm.meb.gov.tr/upload/brosur/2024programortakmetinOnayli.pdf), and [current rollout plans](https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim).

For Study Agent chat, the app asks consent to send the typed question and a bounded local study summary to the selected provider. That summary can include pending/scheduled counts, up to eight subject/topic/tag summaries, up to eight topic-practice aggregates, and up to eight user-entered curriculum references from active mistakes. Those references may include a short outcome note and source URL; they are unverified. Hamartia does not automatically fetch or verify the URL. Consent lists the data categories and excludes saved question-record text/images and previous chats. ChatGPT requests go directly to OpenAI's public Responses API with storage disabled. Configured-endpoint consent names the exact URL, says it may be remote, and discloses that a saved API key is sent there for authentication; the endpoint operator may have separate retention rules.

Practice Session entry sends only the current conversation to the selected provider after consent, without saved study records or the general summary. ChatGPT receives a strict quote-only evidence function; the configured endpoint gets the equivalent evidence-only tool. Hamartia checks quote hints against the host-owned transcript, shows a verified preview, and writes only after explicit approval. The provider cannot write records. Hamartia stores no Study Agent transcript. There is no remote Hamartia proxy or silent provider fallback.

OAuth uses a loopback callback, state, nonce, PKCE, and verified OpenAI ID tokens. Credentials are encrypted with the operating system's protected credential store; Hamartia disables sign-in when that protection is unavailable (including Linux `basic_text`). Sign out attempts to revoke the renewable session and clears local tokens. It retains the nonsecret account registration so the next sign-in can reuse it. Choose **Use a different account** after sign-out to remove that local registration while keeping the installation host ID; manage any remaining OpenAI app registration in ChatGPT settings. If revocation cannot be confirmed, Hamartia reports that and links the next step to ChatGPT settings.

Automated tests mock the OAuth server, identity keys, model list, Responses stream, and configured-endpoint transport. They never use a real ChatGPT account or a local model. Deterministic host verification/create paths are benchmarked with synthetic data and fail-fast provider tripwires; no model execution or inference timing is included. A real ChatGPT subscription sign-in and request, including SIWC tool eligibility, still need manual verification on a supported desktop with an eligible account and OS credential store.

## Non-AI verification

Backend tests from the repository root:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
PYTHONPATH=backend python backend/benchmarks/benchmark_storage.py
PYTHONPATH=backend python backend/benchmarks/benchmark_questions.py
PYTHONPATH=backend python backend/benchmarks/benchmark_backup.py
PYTHONPATH=backend python backend/benchmarks/benchmark_question_order.py
PYTHONPATH=backend python backend/benchmarks/benchmark_practice_sessions.py
PYTHONPATH=backend python backend/benchmarks/benchmark_exam_profiles.py
PYTHONPATH=backend python backend/benchmarks/benchmark_practice_profiles.py
PYTHONPATH=backend python backend/benchmarks/benchmark_mixed_workloads.py
PYTHONPATH=backend python backend/benchmarks/benchmark_clock_api.py
python3 scripts/benchmark_docs.py
```

The desktop social-auth benchmark runs the Firebase JS SDK against a local fake Auth endpoint, simulates the Google browser callback, and exercises profile GET/PATCH through desktop IPC. It blocks all non-loopback networking; its report documents exact commands, results, and provider/database limits:

```sh
npm ci --ignore-scripts --prefix desktop
npm run bench:social-auth --prefix desktop
```

`benchmark_docs.py` parses the checked-in rendered wiki with Python's standard library and makes no network requests. It validates the 17 EN/TR routes, locale attributes, matching navigation and active items, paired section anchors, local links/assets, and 20 rubric entries against exact excerpts in their cited rendered sections and the screenshot protocol. It writes `reports/2026-11-15-docs-benchmark-results.json`. External links are counted but not fetched. The output labels `ai_included: false`.

The exam scoring profile implementation is documented in [`reports/2026-11-15-exam-scoring-profiles.md`](reports/2026-11-15-exam-scoring-profiles.md), with the PracticeSession, focused-timer, Study Agent host-selection, and backup extension in [`reports/2026-11-16-practice-scoring-profiles.md`](reports/2026-11-16-practice-scoring-profiles.md). The practice-summary scaling benchmark uses mixed profile-version fixtures and an independent rational-score/grouping oracle. The persisted API benchmark uses synthetic fixtures and mounts no provider routes.

The task workbook contains ten paired tasks total (20 locale-specific prompts, ten per locale), including cross-page synthesis, false premises, synthetic broken/stale-link decoys, privacy/scope/Clock gates, and fixed-viewport screenshot tasks. `docs/benchmark/answer_key.json` is a separate weighted human rubric with page/anchor evidence. Human administration requires at least two independent single-locale testers per locale, seeded task ordering, and a fresh browser profile per tester. Each tester must score at least 43/50; the two locale cohort means must sum to at least 90/100; every tester must earn full credit on all four critical tasks in their locale. No human runs or screenshots are included in the automated result yet. The task and key files are checked into the repository and therefore inspectable: an evaluator can withhold the key during a session, but this is not a cryptographically sealed or anti-gaming blind test. Screenshots, visual usability, and retrieval accuracy require human administration and scoring.

Frontend:

```sh
cd frontend
npm test
npm run build
npm run bench:clock
npx playwright install chromium
npm run test:browser
```

The browser smoke test uses the `scripts/dev.py` launcher to start real FastAPI and Vite servers with a temporary data directory. It checks missed-question/exam CRUD and review flows; TYT/AYT section create/edit, reload, and capture-missed-question flows; topic net/accuracy charts and full history management; the focused-session counter/pause/reload/complete loop including a successful practice create followed by injected Clock PATCH failure and an idempotent retry; durable legacy-timer migration including a failed-write safety check; countdown/reload, reminder persistence and due-alarm reconciliation while another tab is selected, including retry after an injected reconciliation PATCH failure; clock GET failure write guards; and backup download. Python backend dependencies must be installed for the test; use the active virtual environment or set `HAMARTIA_PYTHON` to the Python executable path.

`npm run bench:clock` compares 96 seeded timer scenarios against a separate iterative oracle, checks DST gap/fold rules, 128 alarms, missed-event idempotency, long-jump boundedness, and explicit negative controls. `benchmark_clock_api.py` separately measures the persisted API and checks failure safety plus backup/restore. Both benchmark outputs label `ai_included: false`. Neither runs local AI or a model. Desktop notification delivery, sleep/wake behavior, and Windows/Linux package UI remain manual platform checks.

These commands do not load a model or send requests to a model endpoint. GitHub Actions runs frontend test/build/browser smoke and backend test/benchmark workflows.
