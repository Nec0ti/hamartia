# 2026-11-14 data backup and restore

## Scope

- Download a ZIP backup from Settings; includes JSON records and `uploads/`, excludes the personal API key.
- Restore via CLI while the app is closed; validate checksum/schema/path/upload references and preserve the existing directory.
- Prevent concurrent writes during restore with an application process lock.
- No AI calls; local AI behavior is out of scope.

## Verification

- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python -m unittest discover -s backend/tests -v` — 59/59 passed.
- `npm test` — 4/4 passed.
- `npm run build` — succeeded; 680.48 KB minified JS and Vite's 500 KB chunk warning.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — passed; actual ZIP download 285 ms, screen navigation 2.293 sec, capture/review persistence 2.336 sec, practice CRUD 1.344 sec, incorrect edit/delete 0.417 sec. No 390 px overflow or browser errors.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_backup.py` — 50 uploads of 2 MiB each (100 MiB): export 8.5842 sec, validation 0.9865 sec, restore 1.0021 sec, ZIP 104,900,138 bytes.
- Storage benchmark in the same session: 1,000 exam append 19.6104 sec (50.99 records/sec), read 0.0099 sec, update 0.0223 sec, delete 0.0249 sec; the 100-question benchmark also passed.

## Data safety

The restore archive is fully validated in a sibling staging directory before being applied. The existing directory remains as a snapshot; if the new directory swap fails, the previous directory is put back. The API key is not written to the backup ZIP and is preserved from the existing setting when restoring on the same computer. On a new computer, the API key remains empty.

## Limits

- The ZIP API client `httpx` emitted a deprecation warning in the test environment; the test passed.
- Benchmarks were measured on the local machine and temporary SSD/tmp space; real user archive sizes can vary.
- The real AI endpoint/model has not yet been verified on another computer.
