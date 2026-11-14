# 2026-11-14 exam context, solve order, and question time

## Scope

When adding a wrong question from exam history, the exam ID is carried over automatically. Optionally record the question number in the exam, the student's own solve order, and time per question. The Study Plan shows early/middle/late solve-order groups and median time per group for wrong questions that remain linked to existing exams.

Only records in the mistake notebook are covered. Since there is no denominator for correct/blank answers, results are not presented as success or accuracy percentages. Deleting an exam does not delete its questions; the relationship is excluded from the solve-order summary.

## Verification

- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python -m unittest discover -s backend/tests -q` — 65/65 passed. Covered legacy record defaults, metadata validation, median, solve-order groups, and deleted-exam relationship.
- `npm test` — 4/4 passed.
- `npm run build` — succeeded in 21.82 sec; JS bundle 683.63 KB minified / 195.17 KB gzip. Vite's 500 KB chunk warning remains.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — passed. Checked adding a wrong record from an exam row, form metadata, view after refresh, early solve order/32 sec median, and question retention after deleting the exam. Smoke timings: navigation 2.253 sec, capture/review 2.423 sec, exam CRUD 2.318 sec, question CRUD 0.354 sec, backup download 0.208 sec. No AI endpoint calls from the browser.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_question_order.py` — summary calculation only: 1,000 records 0.014627 sec (68,368 records/sec), 10,000 records 0.137947 sec (72,492 records/sec). Data preparation and Pydantic object creation time are excluded.
- `PYTHONPATH=backend /tmp/hamartia-venv/bin/python backend/benchmarks/benchmark_questions.py` — regression measurement for the changed question flow: 100 image uploads 0.6005 sec (166.53/sec), list 0.0008 sec, summary 0.0015 sec, text capture 1.1541 sec (86.65/sec); no AI calls.
- GitHub Actions run #61 (`3d84fcc`): frontend and backend jobs succeeded. Backend ran the full test suite and JSON, question, backup/restore, and solve-order benchmarks.

## Data compatibility and limits

New `Question` fields are optional with defaults; no migration is needed for old `questions.json` records. Question number/solve order cannot exceed the related exam's total correct+incorrect+blank count. Time per question is a positive integer number of seconds. The summary aggregates saved wrong questions by exam type and subject; it does not measure full-exam accuracy.

The build warning is due to the existing large bundle. Real local AI was not run or included in benchmarks.
