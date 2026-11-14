# 2026-11-14 topic study sets — implementation and verification

## Scope

A separate topic study set record was added to the Study Plan. Date, subject, topic, correct/incorrect/blank counts, and minutes are stored. The backend calculates net as `correct - incorrect/4` and accuracy as `correct / (correct + incorrect)`; blank questions are excluded from the accuracy denominator. Subject/topic summaries aggregate only these records. Sets can be edited and deleted. `practice_sessions.json` is included in the ZIP backup; if it is missing from an old v1 archive, restore uses an empty list.

## Verification

- Backend: `cd backend && /tmp/hamartia-venv/bin/python -m unittest discover -s tests -q` — 72 tests passed.
- Frontend: `cd frontend && npm test` — 4/4 passed.
- Production build: `cd frontend && npm run build` — succeeded; main JS 689.01 KB minified / 196.30 KB gzip. Vite's 500 KB chunk warning remains.
- Real Chromium smoke: submitted the practice form and verified the saved result after the API response and page reload. Measurements: navigation 2.475 sec, practice persistence 1.436 sec, mistake capture/review persistence 2.850 sec, exam CRUD 3.245 sec, question edit/delete 0.493 sec, backup download 0.262 sec. `ai_included: false`.
- Benchmark: `PYTHONPATH=backend python backend/benchmarks/benchmark_practice_sessions.py` — 1,000 sets/20 topics: summary 0.007639 sec, write 0.017720 sec, read 0.028008 sec; 10,000 sets/20 topics: summary 0.055283 sec, write 0.107469 sec, read 0.317847 sec. The measurement does not load or call a model.
- GitHub Actions run #63 (`c1da9aa`) succeeded with backend and frontend jobs, including the new practice-session benchmark.

## Limitations

The build emits a large chunk warning. Browser timings are local measurements on this machine. The local model and image transfer were not tested on another computer and are not included in these tests/benchmarks.
