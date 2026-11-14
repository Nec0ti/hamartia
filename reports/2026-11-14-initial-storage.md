# 2026-11-14 — initial storage and exam flow

## Scope

Exam creation API logic, JSON history preservation, concurrent writes, and storage microbenchmark. No local AI or model calls were made.

## Checks

`backend/tests/test_exams.py`: 4 checks passed.

- Generate an ID/time from the identity-free payload sent by the UI and preserve the old record.
- Reject an empty subject and a negative correct count.
- Add 32 concurrent records to the same JSON file using different `StorageService` instances.
- Do not modify malformed JSON during append.

The runtime used Python 3.14 and FastAPI 0.141.1/Pydantic 2.13.4 packages from the system Nix store. This does not test the full backend HTTP server or AI routes.

## Benchmark

`backend/benchmarks/benchmark_storage.py` sequentially added and reread 1,000 exam records in a temporary directory. Result: append 12.4065 sec (80.60 records/sec), read 0.0091 sec. Rewriting the whole list on each append makes this synthetic batch load expensive for file-based JSON; it does not represent a typical user's record rate. SQLite should be considered for larger/multi-process use.

## Frontend verification

`npm ci --offline` failed because Vite 5.4.21 was not in the local npm cache. Frontend build and browser smoke were not run; therefore, it has not yet been proven that the entry flow works end-to-end through the UI.
