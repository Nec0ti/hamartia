# Benchmark oracle hardening

Date: 2026-11-15

## Scope

The six non-AI benchmarks now compare full observable outputs or persisted state with precomputed expected values. Fixture generation and expected-value work are outside timed operations. Deterministic wrong-result probes alter a copy of a measured result and must be rejected by the same oracle comparison; mutation probes do not emit or contribute timing samples.

Added boundary and varied data includes empty scores, zero-duration exams, consecutive activity dates, case/whitespace-colliding practice groups, all-blank and high-count practice records, varied question subjects/topics/tags, sectioned TYT order boundaries, a 3,600-second order outlier, legacy review-day fallback, same-day review attempts, reviewed and unclassified questions, invalid question-upload payloads, corrupted backup members, missing upload references, and a ZIP traversal member. Backup failure cases assert the previous target/settings remain intact and do not create a snapshot or leave an archive.

The backend suite also keeps sequential JSON append explicitly stress-only. Multi-process/crash recovery and real loopback HTTP workloads remain separate backlog work. No application production code, local-AI route, model invocation, or provider request is added here.

## Validation

Ran the six default benchmark commands in sequence from the repository root with `PYTHONPATH=backend` in an isolated Python 3.14.8 environment. Combined wall time was about 46 seconds. All six completed successfully; every JSON result included `"ai_included": false` and seed `20261114`.

| Workload | Size | Observed result |
|---|---:|---|
| JSON append stress | 1,000 exams; 309,935 persisted bytes | 13.0867 s append (76.41 records/s); exact post-CRUD state and full progression oracle passed; truncated JSON rejected. |
| Question flow | 24 PNG uploads; 17,905,285 image bytes | Upload 1.0777 s; warm insight p50/p95 0.000777/0.000791 s; varied group/tag oracle, invalid upload rejection, and mutation probe passed. |
| Backup/restore | 24 images; 25,186,280 upload bytes; 25,201,169-byte archive | Export p50/p95 0.937818/0.943044 s; restore 0.109114/0.121658 s; semantic records/settings and image hashes matched; corruption, missing reference and traversal cases rejected. |
| Question order | 1,008 and 10,008 questions, including four section groups | Warm summary p50/p95 0.034454/0.043104 s and 0.392036/0.482630 s; each group’s exam count and stage counts/medians matched; mutation probe passed. |
| Practice history | 1,000 and 10,000 sessions; up to 1,282 groups | Warm summary p50/p95 0.034392/0.035145 s and 0.335641/0.393988 s; every group aggregate and ordered trend matched. |
| Mixed persisted history | 1,500 exams, 2,500 questions, 4,000 sessions; 4,249,174 JSON bytes | Progression, full question insights, review activity and practice trends matched; 16/16 threaded appends preserved; update/delete state matched. |

Environment: Linux `7.3.0-x86_64`, Python `3.14.8`, 8 logical CPUs reported, processor string unavailable. These are local synthetic-data measurements, not performance thresholds or a production corpus. PNG pixels are seeded synthetic noise. Hosted CI has different hardware/software; compare only within a pinned runner and workload manifest.

## Follow-up

See [backlog.md](../backlog.md) for the separate multi-process/crash-injection, loopback HTTP E2E, and blind bilingual documentation retrieval/screenshot benchmark items. Those remain outside this change and continue to exclude AI provider calls.
