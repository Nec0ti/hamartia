# 2026-11-14 local model error handling — implementation and verification

## Change

`AIService._completions()` propagates provider errors instead of converting them into empty responses. The question analysis API returns 502 for `OpenAIError`; the frontend's existing HTTP error flow displays the message. On error, the existing Council analysis and manual tag remain unchanged. This prevents access/model errors from being stored as if they were successful analyses.

## Verification

- Backend: `PYTHONPATH=. python -m unittest discover -s tests -q` — 73 tests passed. The new boundary test produces a fake `OpenAIError` and verifies 502 plus preservation of the record/tag; it does not call a real model or endpoint.
- Frontend: `npm test` — 4/4 passed; production build succeeded, JS 695.22 KB / 198.14 KB gzip. The 500 KB chunk warning remains.
- Chromium browser smoke passed; UI, practice, chart, and backup flows continue to work. Smoke confirms `ai_included: false` and no `/agent` or `/analyze` requests.
- No real AI request or AI benchmark was run.
- GitHub Actions run #69 succeeded with backend and frontend jobs.

## Manual verification on another computer

Follow the manual sequence in the README: analyze a text-only question, then analyze an image question. The second check verifies multimodal endpoint/model support in actual use. Until this is done, connection/model/image transfer should not be considered complete.
