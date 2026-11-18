# Question-analysis consent host benchmark

Date: 2026-11-17

## Scope

Added a persisted host-only benchmark for the existing question-analysis consent path: local preview, one-use approval, mocked HTTP request, and full `Question` persistence. The benchmark uses temporary storage, synthetic question/image/settings fixtures, a fixed `httpx.MockTransport`, and fail-fast socket plus non-mock HTTP transport tripwires. The configured synthetic key is never sent outside that mock. No production app behavior changed.

The timed samples include the local preview route, explicit approval route, request serialization/handling by the fixed mock, and storage save. Untimed probes cover preview/cancel/replay, stale approval, suspended request races, manual-tag preservation, and failure handling.

## Correctness coverage

- An independent exact-value oracle checks the preview's safe authority, scheme, model, payload inclusion categories, and auth categories. It asserts the synthetic key is omitted and that no extra disclosure fields are returned.
- Successful approvals are checked against a complete expected persisted `Question` row. A separate full-row check proves a manual tag changed during a suspended mocked response survives alongside the saved analysis.
- Preview, cancel/decline, replay, and stale question/settings approvals produce zero mock transport calls. Approval is one-use; question and settings changes during a suspended mocked response return 409 and preserve the latest stored values.
- A mocked transport failure produces exactly one attempt and does not persist analysis. All race and failure probes run outside timed samples.

## Resource measurement

Command:

```sh
PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_question_analysis_consent.py --repeats 3
```

It passed all three repeats on Python 3.14.8, Linux x86_64, with eight logical CPUs. Each repeat measured eight successful approvals. Per-repeat p50 values were 0.015879, 0.016652, and 0.018924 seconds; p95 values were 0.731127, 0.022374, and 0.025122 seconds. The command took 4.70 seconds locally. Each repeat reported 12 mocked transport attempts total, of which eight were timed approvals; provider calls: zero. The timer stops at the approved request response; full-row persistence and replay checks run outside timing. These are host-path plus synthetic mock-transport measurements; they do not measure a provider, model, endpoint latency, or real credentials. CI uses Python 3.12 and runner timing may differ.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend.tests.test_questions backend.tests.test_question_analysis_consent`: **60/60 passed**.
- `python .github/scripts/test_release_metadata.py`: **6/6 passed**.
- `git diff --check`: passed.
- The exact benchmark command with `--repeats 3` passed. Every repeat reported zero transport calls for preview/cancel/replay/stale-before-dispatch, exactly one mock attempt per approved request, full-row agreement, both suspended race conflicts, preserved manual tag, and one attempt on failure.
- Backend CI includes the benchmark with three repeats; its PR workflow run remains pending.
- The benchmark workflow step still requires a passing PR CI run. No provider, local model, physical-device check, human evaluation, external service, or live network request was performed.

No provider, local model, physical-device check, human evaluation, external service, or live network request was performed.
