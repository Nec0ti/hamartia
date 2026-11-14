# Cosmos write safety — 2026-11-14

## Scope

- A storage operation that reads and updates one JSON document under the same file lock.
- Protect concurrent writes in Cosmos node upsert and sector unlock calls.
- Safely disable the assault route, which has no defined rules, stakes XP, and writes to two files.
- Tests, benchmarks, and browser regression without model calls.

## Implemented behavior

- `StorageService.update_doc()` validates existing JSON, creates the default model if missing, runs the callback under the file lock, and saves with an atomic rename. `load_doc()` uses the same file lock.
- Creating a node or incrementing the error count for the same topic/tag is a single `cosmos.json` mutation. Node IDs are unique UUIDs.
- Sector unlock uses the same document mutation; unlocking the same sector a second time does not create another record.
- `POST /cosmos/nodes/{id}/assault` returns HTTP 410. On success, the old route wrote `cosmos.json` and `user.json` separately and awarded XP; on failure, it applied a different penalty, and the schema did not expose a `cleansed` field. This did not define a reliable economy rule.
- The assault route does not read or write JSON. The old frontend API wrapper is retained, but no screen calls this route.

## Verification and measurements

| Check | Result |
| --- | ---: |
| Backend unittest | 38/38 passed |
| Parallel upsert to same Cosmos node | 24 calls, 1 node, 23 increments |
| Parallel upsert to different nodes | 24/24 distinct nodes stored |
| Sector unlock race | 3 different sectors stored once each |
| Assault route | 410, `cosmos.json` and `user.json` bytes unchanged |
| Frontend Node tests | 4/4 passed |
| Frontend production build | 28.68 sec, succeeded |
| Browser smoke regression | 3.035 sec navigation / 3.615 sec capture+review / 1.045 sec exam CRUD |
| 1,000 exam append / read | 19.8911 sec / 0.0135 sec |
| Exam update / delete | 0.0325 sec / 0.0305 sec |
| Single user JSON update | 0.0013 sec |
| Progression calculation | 0.0021 sec |
| Loading 100 image questions | 0.3414 sec / 292.87 records/sec |
| 100 text-only question records | 0.4828 sec / 207.13 records/sec |

Commands:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build
cd frontend && npm run test:browser
```

## Limits

- File locks are process-local; this version is for a single API worker. SQLite or a process-wide lock is needed for multi-worker support.
- The XP assault game rule and UI connection do not exist. XP is not awarded before a learning task can be verifiably completed.
- Browser smoke does not use Cosmos mutations through the UI; node/sector races are checked in backend tests without AI.
- Local AI was not loaded, called, or benchmarked.
- The last successful GitHub Actions run, `43609061343`, was before the Cosmos change; the new run will be verified after this commit is pushed.
