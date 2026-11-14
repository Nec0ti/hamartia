# TYT/AYT sectioned mock exam — results

## Implementation

- A TYT/AYT mock exam is stored in one `Exam` record with section names and correct/incorrect/blank counts. The backend validates totals; duration remains the session duration. XP, streak, and exam count are each calculated once for the same session.
- Branch exams and old TYT/AYT records without sections continue to work. When an old full exam is opened in the edit form, its existing counts are preserved as a single section.
- History shows totals in one row and expands to show subject results. The subject filter calculates statistics/net trend from that section.
- Adding a wrong question from a section carries over the subject name; question number/solve order are validated against the section's question count. The question stores the section size as a snapshot at the time of entry.
- Backup restore round-trips the new `sections` field; defaults are preserved for old JSON/backup fields.

## Verification

- Backend: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -q` — 81 tests passed.
- Frontend: `npm test` — 7 tests passed.
- Frontend production: `npm run build` — succeeded. Existing large bundle warning: 699.82 KB minified / 199.51 KB gzip.
- Chromium smoke: `npm run test:browser` — succeeded. Includes branch and TYT/AYT creation, TYT reload, adding a wrong question from a section, editing, subject filter, and deletion. Total `exam_crud_ms`: 10,840 ms; other steps were measured in command output.
- `git diff --check` — clean.

## AI-free benchmark measurements

Single runs on the local development machine; each script ended with success assertions. Measurements depend on machine/load and are not CI performance thresholds.

| Flow | Data | Result |
| --- | --- | --- |
| JSON exam storage | 1,000 records, 10 full exams | append 19.2337 sec (51.99 records/sec), read 0.0206 sec, update 0.0489 sec, delete 0.0374 sec, progression 0.0051 sec |
| Question capture/insights | 100 with images + 100 text-only, 40 section-linked | upload 0.8938 sec, text capture 1.2757 sec, section-question upload 0.6774 sec, section solve-order summary 0.0091 sec |
| Backup/restore | 50 x 2 MiB uploads, ZIP 104,900,284 bytes | export 6.8527 sec, validation 1.0435 sec, restore 1.1368 sec |
| Question solve-order summary | 1,000 / 10,000 records | 0.016647 / 0.178777 sec |
| Topic study set | 1,000 / 10,000 sessions | summary 0.009912 / 0.076962 sec; write 0.022863 / 0.172899 sec; read 0.049215 / 0.400616 sec |

`ai_included:false` appeared in all benchmark outputs. No real model was loaded or endpoint called.

## Git transfer and remaining work

- Local UI commit `040462e2bf9a73271d622741b63c9cd616c1ceb4`; remote counterpart `de19c4f56883d460eac80649e18b54468135dbcf`. The tree SHA of both is `8bed8506808519c6812b31fc9528e130fc172c74`.
- Local backup/benchmark commit `a7f7b556488418857d86ad812217a63157586960`; remote counterpart `7c8b57a87447540484bb64259d7b5876e2d11e5b`. Tree SHA is `9cc28a65ae406a2915be33dd7ee7618e9274144f`.
- The GitHub `codex/hamartia-rebuild` ref was fast-forward updated and PR #1 was opened against `master`. GitHub Actions run #84 for PR head commit `a2746a104ad61f8857a405aa7a7ce599c3344696` completed successfully; backend and frontend jobs passed.
- Since the checkout has no live `backend/data`, the user's real JSON records were not tested. Endpoint/model and image-analysis verification in P3 will be done manually on another computer.
