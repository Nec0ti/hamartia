# Multi-process storage and loopback HTTP benchmark

## Scope

This adds the two remaining non-AI system benchmark paths in P2: independent-process storage writers, abrupt process death at the atomic-replace boundary with a fresh-process recovery check, and real serialized HTTP requests over loopback with concurrent clients. Direct storage append timing is reported separately. Correctness, injected failure, and oracle-sensitivity checks are outside every timing interval.

`StorageService` mutations now hold the existing in-process locks plus an OS process lock on `.<data-dir>.mutation.lock` in the data directory's parent. The lock path uses the resolved canonical data directory so relative and symlink aliases agree. POSIX uses blocking `flock`; Windows retries one-byte `msvcrt` nonblocking acquisition until available, while propagating non-contention errors and allowing interruption. The lock is reentrant within a thread, so multi-file question upload/delete and backup snapshot capture share the same process guard with nested storage mutations. The API still reserves the data directory for its full process lifetime, so this does not enable multiple simultaneous API servers.

The HTTP path starts the real FastAPI app in a child process with a temporary data directory. The parent and child reject socket `connect` calls to anything except a loopback IP or `localhost`. The client validates the exact `127.0.0.1` base URL and calls only `GET`/`POST /exams`; it never contacts Settings or Study Agent routes. No provider, model, or AI code path is invoked.

The generated persisted-record oracle is independently built from worker IDs, ordinals, and values, and compares complete records after processes exit. The restart fixture is hand-authored (`hand-a:17`, `hand-b:0`, `hand-c:-3`) and includes a newly committed post-restart row. HTTP requests use two deterministic seeds (`1729`, `20261115`) over explicit zero-result, all-blank, repeated-date/repeated-subject, and mixed-result vectors; an additional 4 KiB subject checks serialized payload size. A full independently constructed response oracle checks every input/default/metadata field, net, total, XP, generated UUID, and UTC creation time; persisted state must exactly equal these expected responses. A same-ID/same-payload `net` corruption probe confirms the oracle rejects a wrong computed value.

## Results

Command, Python 3.14.8 on Linux 7.3.0, 8 logical CPUs:

```sh
PYTHONPATH=backend python backend/benchmarks/benchmark_system_resilience.py --json-output /tmp/system-benchmark.json
```

| Experiment | Input and result |
| --- | --- |
| Multi-process writers | 4 simultaneously released processes × 8 records; 32/32 complete expected records persisted in 0.163906 s. The missing-record perturbation was rejected. |
| Atomic replacement crash | Child exited with code 73 after writing/fsyncing the temp file and immediately before replace. Fresh storage service read the 3 prior committed records; it ignored the orphan temp file. A new append then produced the exact expected 4-record state and removed the temp file. |
| Loopback serialized HTTP | 4 clients × 4 requests × 2 seeds = 32 POST requests; 8,597 request bytes and 12,536 response bytes, including one 4 KiB subject. Full expected response and persisted-state oracles passed; the same-ID `net` corruption probe was rejected. Request p50/p95: 0.015606/0.023239 s; concurrent wall 0.132771 s (241.017 requests/s). |
| Direct storage baseline | 32 validated `Exam` appends without HTTP/socket serialization; p50/p95 0.002111/0.005018 s. |

The HTTP measurements include TCP loopback, HTTP serialization, routing, Pydantic validation/response serialization, and persistent JSON write. The direct measurement is a sequential `StorageService.append_list` call with the same record count and is not an equivalent concurrent workload; the two figures are kept distinct for that reason.

## Verification

- `PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_storage_process_lock.py -v` — passed (a held-lock writer remained blocked until release; three writer processes persisted 12 unique records).
- Full default benchmark command above — passed; JSON has `ai_included:false`, 32/32 storage rows, exit/recovery evidence, and 32/32 serialized API records.
- `PYTHONPATH=backend python -m unittest discover -s backend/tests -q` — 120 tests passed.
- `python -m compileall -q backend/benchmarks/benchmark_system_resilience.py backend/app/services/storage.py` — passed.
- `git diff --check` — clean.
- CI runs the bounded benchmark on Ubuntu and the deterministic held-lock/contention tests in the Windows/Linux packaging matrix.

## Limits

Results are a synthetic single-machine sample, not a performance target. The abrupt-death point is immediately before `Path.replace`; the crash/restart experiment runs on Linux CI and locally, and validates that a fully written temp file cannot corrupt the previous complete file. It does not simulate power loss, torn filesystem metadata, disk-full conditions, or every crash point; Windows crash replacement behavior is not claimed as verified. The HTTP request mix is limited to `/exams`, and concurrency is capped at eight clients. The deterministic held-lock and multi-writer process tests run in both Windows and Linux packaging CI. Multi-process direct storage mutations are serialized, but multiple API server processes remain prevented by the lifetime `DataDirectoryLock`.
