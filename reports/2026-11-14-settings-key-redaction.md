# Settings API key redaction

## Result

`GET /settings` and `PATCH /settings` no longer send the saved API key to the browser. Responses contain only the `has_api_key` boolean field. Updating with an empty key preserves the saved key; a new value replaces it, and an explicit `clear_api_key` request clears it. The UI does not fill the key field from the server response and clears a typed key from React state when the modal closes.

## Checks

- Backend: Python 3.14 `.venv` environment, `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -q` — **76/76 passed**. New tests cover GET/PATCH redaction, preservation, replacement, and clearing.
- Frontend: `npm test` — **4/4 passed**.
- Production build succeeded: JS **695.72 KB / 198.31 KB gzip**. Vite's 500 KB chunk warning remains.
- Real Chromium browser smoke passed. The add/remove API key flow verified that responses contain no API key and that it was cleared on disk; **1.014 ms** in the last run.
- Last successful full browser smoke timings (ms): navigation **3806**, topic set persistence **2080**, focused session **7537**, trend/full history **2801**, wrong-question save+review persistence **4134**, exam CRUD **4307**, wrong-question edit/delete **901**, backup download **309**. `ai_included: false`.
- Backend AI-free benchmarks: 1,000 exam JSON append **23.4282 sec** (42.68 records/sec), read **0.0087 sec**; 100 wrong-question flow image upload **0.4985 sec**, text capture **0.7865 sec**, list **0.0021 sec**, insight **0.0063 sec**; 50 x 2 MiB backup export/validation/restore **5.6322 / 0.9249 / 0.9199 sec**; question solve-order summary at 1,000/10,000 records **0.013671 / 0.139487 sec**; topic set summary at 1,000/10,000 records **0.013875 / 0.074794 sec**.
- No benchmark called a model. This code changes only the settings storage/response path; benchmark numbers depend on machine load and filesystem performance.
- GitHub Actions #73: the frontend smoke harness read a concurrently changing practice response through a Promise callback and asserted an old record. The assertion was attached to the endpoint's directly awaited response; after the fix, workflow #74 passed.

## Implementation note

When tests were first run with system Python, they stopped during import because FastAPI/Pydantic were unavailable in that environment. The ignored repo `.venv` was created, `backend/requirements.txt` was installed, and the full backend suite was run successfully again. The first Playwright Chromium binary could not find the system `glib` library; smoke passed with the Nix Chromium binary.

## Limit

The API key is no longer in HTTP responses or modal state. The single-user localhost app does not prevent unauthorized local processes on the same machine; that would require an OS secret store or a separate user boundary. No real local model call was made; this remains in the backlog for verification on another computer.
