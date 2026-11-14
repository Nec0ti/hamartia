# Today's study activity

## Scope

- The Study Plan card shows the number of different questions answered today and total correct/incorrect answers.
- If the same question is answered again during the day, the question metric increases by one; result counters increase for every answer.
- Values are calculated from the `review_attempts` list; no new storage field, setting, or data migration.
- The activity date is compared with the ISO attempt day component used by the spaced-review code.

## Verification

- `PYTHONPATH=. /tmp/hamartia-venv/bin/python -m unittest discover -s tests -v` — 45/45 passed.
- `npm test` — 4/4 passed.
- `npm run build` — passed in 22.12 sec. Bundle 679.49 KB minified / 194.02 KB gzip; the 500 KB chunk warning remains.
- Chromium browser smoke passed. After incorrect/correct answers and refresh, it showed 2 different questions, 1 correct answer, and 1 incorrect answer. No AI endpoint call; no horizontal overflow or frontend/API/console errors.
- Smoke timings: navigation 2.157 sec, capture+review persistence 2.335 sec, exam CRUD 1.234 sec, question edit+delete 0.409 sec.
- 100-question local-flow benchmark: insight 0.0053 sec; upload 0.604 sec, list 0.0008 sec, attempt 0.0034 sec, review 0.0038 sec, edit/delete 0.0045/0.0030 sec, text capture 0.4463 sec. `ai_included: false`.

## Limits

- The model was not loaded and AI was not called; local AI will be verified on another computer.
- As with the existing scheduler, the day calculation uses the date component of the saved ISO timestamp and the backend's `date.today()` value. If the backend is moved to a computer in another time zone, the day boundary may differ from the user's local day.
- The benchmark is a single local run, not a performance claim across hardware.
- GitHub Actions run #49 (`d0cd18ff`) for the code commit successfully completed frontend test/build/browser smoke and backend test and benchmark steps. The docs-only run containing this report update is still running.
