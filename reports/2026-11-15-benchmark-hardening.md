# 2026-11-15 — repeatable AI-free benchmark hardening

## Scope and method

Reworked the five existing benchmark areas and added a persisted mixed-workload benchmark. Fixtures are deterministic (`seed=20261114`), schema-valid, varied by subject/topic/date and file size, and stored in temporary directories. Timed paths assert their results; summary workloads include an independently calculated oracle. Repeated paths report p50/p95 and each JSON result includes Python, platform, CPU count, and seed. `--json-output PATH` saves the machine-readable result.

First-access measurements mean the first application-level load or summary after fixture creation. The operating-system page cache is not cleared, so these are not disk-cold measurements. Warm results include a warmup, then repeated runs. Timings are observations from one local machine, not CI thresholds.

## Workloads and results

Machine: Linux 7.3.0, Python 3.14.8, 8 logical CPUs, 15 GiB RAM. The reported processor model was unavailable.

| Area | Seeded workload | Result |
| --- | --- | --- |
| Storage stress | 1,000 sequential exam appends; 10 full mocks; then repeated read, update, delete, document update, and progression | Append 12.8056 s (78.09/s); first read 0.0107 s; update p50/p95 0.023290/0.027794 s; delete 0.022919/0.025294 s; progression 0.012659/0.014157 s |
| Question capture | 24 valid PNG uploads (256×256 to 1024×768; 17,905,285 bytes), then 24 text records, 24 section-linked records, insights, attempt, review, update, delete | Image batch 1.0871 s; text batch 0.0555 s; section batch 0.0754 s; list p50/p95 0.000248/0.000283 s; insights 0.000564/0.001936 s; repeated update/delete each passed |
| Backup and restore | 24 valid seeded PNG files (256×256 to 1024×768); exam/question/settings JSON with upload references; restore into existing data and preserve snapshot; three measured repeats | 25,186,280 upload bytes; 25,200,816-byte archive; export p50/p95 0.925850/0.951665 s; validation 0.108246/0.108444 s; restore 0.112550/0.121312 s; upload hashes and restored JSON values matched |
| Solve-order summary | Persisted 1,000 questions / 50 exams and 10,000 questions / 500 exams; distinct question numbers and solve orders, varied subject and time | p50/p95 0.023410/0.026258 s and 0.283019/0.318193 s; every stage count and median matched an independent oracle; unknown, missing-order, and out-of-range rows were excluded |
| Practice summaries | Persisted 1,000 and 10,000 sets across 8 subjects and up to 160 topics | p50/p95 0.033401/0.035113 s and 0.350428/0.373663 s; all sessions and topic groups accounted for |
| Mixed persisted flows | 1,500 exams, 2,500 correctly linked missed questions, 4,000 practice sets; full-history calculations; 10 measured updates, 10 measured deletes, 16 competing appends with 4 workers | JSON sizes 537,993 / 1,842,179 / 1,148,871 bytes; question insight p50/p95 0.119189/0.167687 s; practice summary 0.129740/0.166570 s; 16/16 appends persisted; chronological due/scheduled review data and independent progression, review/order, and practice oracles passed |

The sequential append benchmark is deliberately labeled **stress-only**: it rewrites the full growing JSON array on each append and therefore has O(n²) total serialization/write work. The mixed workload seeds persisted collections once and measures independent reads, summaries, updates, deletes, and concurrent appends to represent a more varied use pattern.

## Verification

- All six AI-free benchmark commands completed successfully and emitted JSON artifacts.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -q` — 93 tests passed.
- `python -m compileall -q backend/benchmarks` — passed.
- `git diff --check` — clean.
- No local model was loaded or called. No production application code or personal data was used.

## Limits

Fixtures are deterministic but synthetic. The question-upload PNG files are valid generated pixel data, but their content is random noise; backup and upload workflows do not include image understanding. The results do not cover a live user's data distribution, process-cold startup, multi-process writers, or slow/network filesystems. Percentile sample counts are 3–21, depending on the workload. The test run emitted existing Starlette/httpx and `datetime.utcnow()` deprecation warnings plus temporary-file resource warnings; tests still passed.

The complete output is in [2026-11-15-benchmark-results.json](2026-11-15-benchmark-results.json). Reproduce from the repository root with:

```sh
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_storage.py --json-output /tmp/storage.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_questions.py --json-output /tmp/questions.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_backup.py --json-output /tmp/backup.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_question_order.py --json-output /tmp/order.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_practice_sessions.py --json-output /tmp/practice.json
PYTHONPATH=backend .venv/bin/python backend/benchmarks/benchmark_mixed_workloads.py --json-output /tmp/mixed.json
```
