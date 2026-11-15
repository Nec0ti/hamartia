# Non-AI benchmark quality follow-up

Date: 2026-11-15

## Scope

This follow-up tightens the persisted question, backup, and mixed-history benchmarks. Question records are compared as complete persisted objects after upload, tagging, attempts, review, edits, deletes, text capture, and section-linked capture. The final question-insights response is checked against an independently constructed oracle for review state, same-day counts, topic groups, curriculum references, and order buckets.

Two untimed fault probes exercise real question API operations while an injected atomic-write fault silently drops (1) the appended question record and (2) a recorded review attempt. The API still reports success; the full-state oracle must reject the resulting stored state. These probes demonstrate detection of these two named persistence faults only. They do not mutate production source or establish coverage for arbitrary defects. The earlier oracle comparator self-checks remain separate.

Fixtures now have uneven topic and subject frequencies, recent-heavy dates with older history, short/paragraph/long text sizes, and valid seeded PNG blobs with varied dimensions and compressibility. The mixed workload includes up to 64 bounded image files. Backup data now includes a scaled exam history and practice-session history, and restore equality checks cover both along with questions, settings, and upload hashes. All generated data is deterministic from seed `20261114`; injected faults run outside all performance samples.

No production application code or local-AI path was added or changed. No AI provider was called. Every benchmark result contains `"ai_included": false`.

## Validation

Ran the six default benchmark scripts sequentially using Python 3.12.15 on Linux `7.3.0-x86_64-with-glibc2.44` with 8 logical CPUs reported. Combined wall time was 63.27 seconds. Every script succeeded and emitted `ai_included:false` with seed `20261114`.

| Benchmark | Default data and observed checks |
|---|---|
| Storage | 1,000 exams / 309,935 JSON bytes; full CRUD/progression oracle passed; sequential append stress 18.4979 s (54.06 records/s); truncated JSON rejected. |
| Questions | 24 uploads / 17,183,080 image bytes; complete persisted-state checks and full post-mutation insights oracle passed; both injected write faults were detected; invalid inputs left records unchanged. |
| Backup/restore | 96 exams, 24 questions, 96 practice sessions; 28,612,786 upload bytes with per-file sizes 19,174–3,688,548 bytes; 28,624,545-byte archive; export p50/p95 1.161728/1.172073 s, validation 0.135085/0.136883 s, restore 0.138502/0.139877 s; complete record/settings and upload checks passed. |
| Question order | 1,008 and 10,008 questions; unique positions, per-stage counts/medians, and invalid references matched the oracle. |
| Practice history | 1,000 and 10,000 sessions; every aggregate and ordered trend matched the oracle. |
| Mixed persisted history | 1,500 exams, 2,500 questions, 4,000 practice sessions; 64 image references / 6,095,309 bytes (19,167–194,177 bytes each) and 993,890 question-text characters; full progression, question-priority, practice, update/delete, and threaded append checks passed. |

Exact command sequence:

```sh
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_storage.py
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_questions.py
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_backup.py
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_question_order.py
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_practice_sessions.py
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_mixed_workloads.py
```

Focused bounded checks also passed:

```sh
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_questions.py --count 9 --repeats 3
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_backup.py --files 4 --repeats 3
PYTHONPATH=backend /tmp/hamartia-bench-env/bin/python backend/benchmarks/benchmark_mixed_workloads.py --exams 20 --questions 21 --sessions 25 --repeats 5
```

Full machine-readable outputs and per-script wall times are in [the JSON results artifact](2026-11-15-benchmark-quality-results.json). These measurements are synthetic local results, not performance thresholds or a production user corpus. The image fixtures are generated PNGs rather than real student uploads. Multi-process/crash recovery and loopback HTTP E2E remain separate backlog work.
