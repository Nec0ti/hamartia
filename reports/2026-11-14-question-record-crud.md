# Wrong-question record editing and safe deletion

## Scope

- Subject, topic, and text fields can be edited on a wrong-question card.
- Editing preserves the image, analysis response, error tag, and solution/review history.
- Deletion requires confirmation; only an image file whose resolved path is inside `uploads/` is also removed.
- Clearing the text of a question with no image is rejected with `422`; a missing record returns `404`.
- New endpoints use the existing atomic list mutation, `StorageService.update_list`.

## Verification

- `PYTHONPATH=. /tmp/hamartia-venv/bin/python -m unittest discover -s tests -v` — 43/43 passed.
- `npm test` — 4/4 passed.
- `npm run build` — passed in 23.50 sec. Main bundle 679.05 KB minified / 193.94 KB gzip; Vite warns about the 500 KB chunk size.
- `HAMARTIA_PYTHON=/tmp/hamartia-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — passed. Verified edit and delete requests with image, JSON persistence, image removal, no overflow at 390 px, and no requests to AI endpoints.
- Browser smoke: navigation 2.362 sec; capture+review persistence 2.335 sec; exam CRUD 1.301 sec; question edit+delete 0.423 sec.
- `backend/benchmarks/benchmark_questions.py` — 100 questions: upload 0.3006 sec, list 0.0007 sec, insight 0.0121 sec, attempt 0.0041 sec, review 0.0059 sec, update 0.0047 sec, delete 0.0041 sec, text capture 0.4759 sec (210.14/sec).
- `backend/benchmarks/benchmark_storage.py` — 1,000 exams: append 12.8297 sec (77.94/sec), read 0.0077 sec, update 0.0278 sec, delete 0.0241 sec, document update 0.0015 sec, progression 0.0016 sec.

## Limits

- No tests or benchmarks called a model; local AI will be verified on another computer.
- The two backend benchmarks ran concurrently; timings may have been affected by machine load and are not comparisons across hardware.
- A JSON list and file deletion cannot form one transaction. If the process stops after the record is removed from the list, an orphan image may remain; the delete route reports the error in that case. Files outside the directory are not deleted.
- GitHub Actions run #47 (`f372b2f4`) successfully completed frontend test/build/browser smoke and backend tests and both benchmarks.
