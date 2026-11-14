# Local application launcher

## Scope

- `scripts/dev.py` starts FastAPI and Vite together from the repo root.
- It does not show the startup-complete message until the API returns `/healthcheck/ready` and the frontend returns HTTP 200.
- Ctrl+C/SIGTERM stops both child processes.
- The frontend port defaults to 5173 and is configured with `HAMARTIA_FRONTEND_PORT`. Vite uses `--strictPort`, so silent port changes cannot cause a readiness error.
- If Python dependencies or npm installation are missing, report a clear error before running.

## Verification

- Real launcher smoke with a temporary data directory and port 5174: API ready and frontend 200; ports 5174/8000 closed after Ctrl+C. The Cygnet Vite process already using port 5173 remained running. Readiness and clean shutdown after process-group cleanup took 2.458 sec total.
- The 5173 conflict smoke verified the launcher exits with code 1, stops its API child, and preserves the existing application on port 5173.
- `npm test` — 4/4 passed.
- `npm run build` — passed in 26.07 sec. Bundle 679.49 KB minified / 194.02 KB gzip; the 500 KB chunk warning remains.
- `npm run test:browser` — passed through the real `scripts/dev.py`. Smoke ran on port 5174 with a temporary `HAMARTIA_DATA_DIR`; verified exam and question CRUD, today's study summary, page refresh, no overflow at 390 px, and no requests to AI endpoints.
- Browser smoke timings: navigation 2.056 sec; capture+review persistence 2.288 sec; exam CRUD 1.217 sec; question edit+delete 0.471 sec.

## Limits

- The launcher ran in a Linux/NixOS environment; Windows process-tree behavior was not tested separately.
- The API port is fixed at 8000; a port conflict causes API startup to fail at readiness. Only the frontend port is configurable.
- AI was not loaded, called, or benchmarked.
- After the browser smoke job failed to return for a long time on older launcher commits, POSIX child process-group teardown was added and the real browser smoke passed again. GitHub Actions run #54 verifies this final fix.
