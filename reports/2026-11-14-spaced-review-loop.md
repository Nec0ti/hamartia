# Spaced wrong-question review loop — 2026-11-14

## Scope

- Store each attempt to solve a wrong question and whether the result was correct/incorrect locally.
- Calculate the next review date deterministically; preserve old `reviewed_at` records.
- Open a due question and save its result in the Study Plan.
- Real browser + FastAPI smoke, narrow-screen layout, and basic accessibility names.
- AI-free backend/frontend validation and performance measurement for this flow.

## Review rule

- An unattempted question immediately enters the solve queue.
- An incorrect answer is scheduled for the next calendar day and resets the correct streak.
- After a correct answer, wait 1, 3, 7, 14, then up to 30 days, based on the consecutive-correct count.
- The old `reviewed_at` value preserves the question archive. A new solve attempt clears this marker and reschedules the question.
- Old JSON files lack `review_attempts`, so the schema uses a default empty list; no file migration is required.
- XP generation is not tied to this operation; XP is calculated from exam records.

## Implemented paths

- `POST /questions/{id}/attempt` adds a correct/incorrect result within a locked read-modify-write using `StorageService.update_list`.
- `review_state()` calculates the date, consecutive-correct streak, and next review day without a model.
- `GET /questions/insights` returns the due-question queue and the number to be opened later.
- Study Plan displays the image/text, provides correct/incorrect solve buttons, and reloads the plan after saving.
- The wrong-question API accepts image or text records. If there is no image, save an empty `image_name`/`image_path`; adding a new attempt list to the existing record schema is backward compatible.
- Browser smoke uses Playwright Chromium, a temporary `HAMARTIA_DATA_DIR`, live FastAPI, and Vite. A question without an image is added through the form; an image question is saved with an incorrect result, and a text-only question with a correct result. After page refresh, JSON files are read to verify both records persist. The same smoke confirms no requests to AI routes, image upload, accessible button names, and no horizontal overflow at 390 px.
- The browser smoke's `HAMARTIA_DATA_DIR` config override writes test data outside `backend/data`. Normal use does not change the default directory.

## Verification and measurements

| Check | Result |
| --- | ---: |
| Backend unittest | 29/29 passed |
| Frontend Node tests | 4/4 passed |
| Frontend production build | 20.91 sec, succeeded |
| Main JS bundle | 673.35 KB minified / 192.80 KB gzip |
| Online `npm audit` | 0 findings |
| 1,000-record JSON append / read | 21.0752 sec / 0.0078 sec |
| XP/streak calculation for 1,000 records | 0.0017 sec |
| Upload / throughput for 100 image questions | 0.4674 sec / 213.97 records/sec |
| Question list / Study Plan calculation | 0.0011 sec / 0.0129 sec |
| Save solve result / old archive marker | 0.0034 sec / 0.0049 sec |
| Capture 100 text-only questions / throughput | 0.6439 sec / 155.29 records/sec |
| Browser smoke navigation / text capture + result + persistence | 2.715 sec / 2.432 sec |

Commands:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build && npm audit
cd frontend && npm run test:browser
```

## Limitations

- Browser smoke tests upload and result persistence with two questions (one seeded image, one new text-only); correct-answer intervals across all 1/3/7/14/30 day steps are covered by unit tests, not in the browser.
- Local AI was not loaded, called, or benchmarked.
- The bundle continues to trigger the 500 KB warning.
- JSON file locks are scoped to one process; multiple server workers are not supported.
- CI will separately verify Chromium smoke and current backend benchmarks in a documentation commit after this report.
