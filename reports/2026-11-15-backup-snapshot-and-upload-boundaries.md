# 2026-11-15 backup snapshot and upload boundaries

## Scope

- Reject uploads when `data/uploads` is a symbolic link or resolves outside the configured data directory. Keep image creation and question-record insertion in one short mutation section; stage and validate request bytes before taking the lock.
- Use one path resolver for upload creation, question-image serving/deletion, and image inclusion in question-analysis prompts. It rejects a symlinked upload root, symlink path components, and paths outside the uploads folder.
- Apply the same per-data-directory process lock to all `StorageService` writes and question image creation/deletion.
- Capture sanitized JSON and uploads under that lock, then build the ZIP from the temporary snapshot after releasing it. The running API already owns the cross-process `DataDirectoryLock` for its lifetime, so the backup route does not try to acquire that restore-only lock.
- Keep existing restore validation, API-key exclusion/preservation, staged swap, rollback, and old-directory snapshot behavior.

## Verification

- `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python -m unittest discover -s backend/tests -q` — 98/98 passed.
- Focused backup tests — 19/19 passed; question tests — 26/26 passed. Added a deterministic export/write race test, symlinked upload-root upload/delete/image-serving tests, an image-file symlink test, and an oversized-upload test.
- `git diff --check` — passed.
- `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python backend/benchmarks/benchmark_backup.py --json-output /tmp/hamartia-backup-consistency-backup.json` — correctness passed; 24 files / 25,186,280 upload bytes; export p50 0.948 sec, restore p50 0.117 sec.
- `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python backend/benchmarks/benchmark_questions.py --json-output /tmp/hamartia-backup-consistency-questions-final.json` — correctness passed; 24 image uploads in 1.085 sec; `ai_included: false`.
- `PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python backend/benchmarks/benchmark_mixed_workloads.py --json-output /tmp/hamartia-backup-consistency-mixed.json` — correctness passed with 1,500 exams, 2,500 questions, and 4,000 practice sessions; `ai_included: false`.

All tests and benchmarks used synthetic local data. The image-prompt resolver was verified by source review only; no AI prompt execution, provider call, or local model was used.

## Limits

- The process-local lock coordinates the single API process and its `StorageService` instances. The lifetime `DataDirectoryLock` still prevents offline restore while the API is running. Direct manual edits to data files by another process are outside this lock contract.
- Restore still snapshots the previous data directory before replacing it; automatic cleanup of old snapshots is not part of this change.

## Integration after PR #10

The branch was updated by an ordinary merge of origin/master at `89c3173` so the backup and upload changes include the local-calendar review-day schema/API/UI changes. The backup round-trip test for `ReviewAttempt.attempt_day` is preserved alongside the live-write snapshot test.

- Backend: 103/103 tests passed. Focused backup tests: 20/20; question tests: 27/27.
- Frontend: 18/18 tests passed; `npm run build` passed with the existing large-chunk warning.
- Browser smoke: passed with `ai_included: false`; the new attempt day persisted and the `/questions/insights?today=...` request used the same local day.
- AI-free backup benchmark: 24 files / 25,186,280 upload bytes; export p50 0.921 sec, validation p50 0.116 sec, restore p50 0.112 sec.
- AI-free question benchmark: 24 image uploads in 1.055 sec. Mixed persisted workload correctness passed at 1,500 exams, 2,500 questions, and 4,000 practice sets.
