# 2026-11-15 — repeatable AI-free benchmark hardening

## Scope and method

Reworked the five existing benchmark areas and added a persisted mixed-workload benchmark. Fixtures are deterministic (`seed=20261114`), schema-valid, varied by subject/topic/date and file size, and stored in temporary directories. Timed paths assert their results; summary workloads include an independently calculated oracle. Repeated paths report p50/p95 and each JSON result includes Python, platform, CPU count, and seed. `--json-output PATH` saves the machine-readable result.

First-access measurements mean the first application-level load or summary after fixture creation. The operating-system page cache is not cleared, so these are not disk-cold measurements. Warm results include a warmup, then repeated runs. Timings are observations from one local machine, not CI thresholds.

## Workloads and results

Machine: Linux 7.3.0, Python 3.14.8, 8 logical CPUs, 15 GiB RAM. The reported processor model was unavailable.

| Area | Seeded workload | Result |
| --- | --- | --- |
| Storage stress | 1,000 sequential exam appends; 10 full mocks; then read, update, delete, progression | Append 14.4898 s (69.01/s); read 0.0080 s; update 0.0395 s; delete 0.0224 s; progression 0.0017 s; warm read p50/p95 0.009444/0.009914 s |
| Question capture | 100 image uploads (4–48 KiB signature-valid deterministic payloads), then 100 text records, 40 section-linked records, insights, attempt, review, update, delete | Image upload batch 0.8496 s; text batch 0.8017 s; section batch 0.3632 s; list p50/p95 0.001639/0.002003 s; insights 0.001738/0.002462 s; correctness assertions passed |
| Backup and restore | 24 valid seeded PNG files, mixed 320×240 to 800×600; real exam/question JSON with upload references; three measured repeats | 18,909,752 upload bytes; 18,922,452-byte archive; export p50/p95 0.726349/0.731713 s; validation 0.079556/0.079843 s; restore 0.078190/0.082439 s; upload hashes matched |
| Solve-order summary | Persisted 1,000 questions / 25 exams and 10,000 questions / 250 exams; varied subject, exam size, solve order, time | p50/p95 0.020367/0.020954 s and 0.234798/0.266348 s; stage totals matched an independent oracle |
| Practice summaries | Persisted 1,000 and 10,000 sets across 8 subjects and up to 160 topics | p50/p95 0.030079/0.032340 s and 0.309309/0.340983 s; all sessions and topic groups accounted for |
| Mixed persisted flows | 1,500 exams, 2,500 missed questions, 4,000 practice sets; full-history calculations; 10 updates, 10 deletes, 16 competing appends with 4 workers | JSON sizes 535,292 / 1,841,774 / 1,148,859 bytes; question insight p50/p95 0.101278/0.138394 s; practice summary 0.115162/0.120657 s; 16/16 appends persisted; all assertions passed |

The sequential append benchmark is deliberately labeled **stress-only**: it rewrites the full growing JSON array on each append and therefore has O(n²) total serialization/write work. The mixed workload seeds persisted collections once and measures independent reads, summaries, updates, deletes, and concurrent appends to represent a more varied use pattern.

## Verification

- All six AI-free benchmark commands completed successfully and emitted JSON artifacts.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -q` — 81 tests passed.
- `python -m compileall -q backend/benchmarks` — passed.
- `git diff --check` — clean.
- No local model was loaded or called. No production application code or personal data was used.

## Limits

Fixtures are deterministic but synthetic. Image upload timing exercises the existing signature check and file write, not pixel decoding; backup uses valid generated PNG pixels. The results do not cover a live user's data distribution, process-cold startup, multi-process writers, or slow/network filesystems. Percentile sample counts are 3–21, depending on the workload. The test run emitted existing Starlette/httpx and `datetime.utcnow()` deprecation warnings plus temporary-file resource warnings; tests still passed.

The complete output is in [2026-11-15-benchmark-results.json](2026-11-15-benchmark-results.json). Reproduce from the repository root with:

```sh
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_storage.py --json-output /tmp/storage.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_questions.py --json-output /tmp/questions.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_backup.py --json-output /tmp/backup.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_question_order.py --json-output /tmp/order.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_practice_sessions.py --json-output /tmp/practice.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_mixed_workloads.py --json-output /tmp/mixed.json
```
