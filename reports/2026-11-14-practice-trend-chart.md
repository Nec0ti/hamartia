# 2026-11-14 topic study charts and full history — implementation and verification

## Change

Each subject/topic study card has two small charts using all date-ordered points from saved sets: set net and accuracy using only answered questions in the denominator. A blank-only set produces no point on the accuracy line. Edit/delete actions for the latest six sets are directly visible; older sets can be managed in expanded history. If list/summary requests complete at different times, no invalid action is shown for an unmatched record in the list. The model and backend data format did not change.

## Verification

- Backend regression: 72/72 tests passed.
- Frontend: `npm test` — 4/4 passed.
- Production build succeeded: JS 695.22 KB minified / 198.14 KB gzip; the 500 KB chunk warning remains.
- Chromium smoke: verified single-point, 8-point, same-date, and all-blank-answer charts; no overflow at 390 px; editing and deleting a set older than six; and net/accuracy labels. Practice graph + full-history edit/delete section took 1.420 sec; no AI request.
- AI-free topic set storage/summary benchmark, 20 topics: 1,000 sets — summary 0.007644 sec, write 0.009294 sec, read 0.023394 sec; 10,000 sets — summary 0.043044 sec, write 0.089774 sec, read 0.233654 sec.
- GitHub Actions run #67 succeeded with backend and frontend jobs.

## Limitations

Each topic card contains two charts; the page gets longer if many different topics are saved at once. Existing data represents only sets the user saved. Local AI was not included in these checks and measurements.
