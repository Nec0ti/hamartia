# 2026-11-14 topic study sets — implementation plan

## Problem

The topic list in the Study Plan still shows the number of records awaiting review in the mistake notebook. This count does not measure the total questions studied for a topic or success; it should not be presented as a success percentage.

## User flow

After solving a topic set, the student records the date, subject, topic, correct/incorrect/blank counts, and total duration. The ordered net and accuracy trends of saved sets for the same subject/topic are shown. The record list supports editing and deletion; set data does not change the mistake notebook.

## Data and calculation

- Separate `practice_sessions.json` and `PracticeSession` model; if the file does not exist, open an empty list; do not change the exam/question formats.
- Accuracy is `correct / (correct + incorrect)`; blank answers are excluded from the denominator. Show accuracy as null for a set with blank questions but no answered questions.
- Net is `correct - incorrect / 4`.
- Trend groups only by normalized, exact `subject + topic` matches; do not automatically merge aliases.
- Results apply only to saved study sets; do not present them as all of the user's topic knowledge or an overall success percentage.
- Add the new file to the backup format; keep the old backup manifest version backward compatible or read it with an explicit migration version.

## Change surfaces

- `backend/app/models/schemas.py`, new `backend/app/api/practice.py`, new `backend/app/core/practice.py`, `backend/app/main.py`.
- `frontend/src/services/api.js`, form and saved-set/topic-trend view in the Study Plan.
- Backup schema/default list and tests; API/core/browser tests.
- AI-free trend summary benchmark for 1,000 and 10,000 sets; connect it to CI.

## Acceptance criteria

- Reject negative counts, empty subject/topic, invalid date, and all-zero results; start empty if the old file is absent.
- Save, edit, and delete persist; same-topic trend is displayed in date order.
- Accuracy denominator includes only answered questions; blanks are excluded.
- Backup includes new `practice_sessions.json` data and validates the schema during restore.
- Browser smoke verifies results after refresh; no AI endpoint is called.
