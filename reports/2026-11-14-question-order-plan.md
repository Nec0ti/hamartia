# 2026-11-14 exam context and solve order — implementation plan

## Problem

Exam records store only total correct/incorrect/blank counts and total duration. A wrong-question record does not store the exam ID, question number within the exam, order in which it was solved, or time spent on that question. As a result, error patterns by exam order cannot be seen.

## User flow

When opening the add-wrong-question form from a row in exam history, carry over the subject, exam ID, date, and type context. In the form, the user can optionally add the question number, their solve order, and time per question. The general wrong-question form opened manually continues to work as before.

## Data and calculation

- Add `exam_id`, `question_number`, `solve_order`, and `time_spent_seconds` fields to the `Question` model, defaulting to empty/`None`; do not migrate old `questions.json` files.
- Keep wrong-question records if the related exam is deleted. If the exam ID no longer exists, exclude it from the solve-order summary.
- In the Study Plan, show the count of wrong questions with an existing exam link and required solve-order/time fields, grouped into early/middle/late solve order, and median time per question.
- This summary covers saved wrong questions only; without totals for correct/blank answers, do not produce an accuracy percentage.
- Question number and solve order cannot exceed the exam's total question count; time must be at least one second.

## Change surfaces

- `backend/app/models/schemas.py`, `backend/app/api/questions.py`, `backend/app/core/study_plan.py`
- `frontend/src/tabs/RecentExams.jsx`, `DashboardTab.jsx`, `App.jsx`, `QuestionsTab.jsx`, `StudyPlanTab.jsx`, `frontend/src/services/api.js`
- Backend schema/API/summary tests, frontend form test, and browser smoke.
- AI-free summary benchmark for 1,000 and 10,000 questions.

## Acceptance criteria

- Old question JSON records are read with default fields; new fields remain optional in the current add-question flow.
- A form opened from an exam saves the correct exam context and preserves it after refresh.
- Out-of-range question number/order/time are rejected; deleting an exam does not delete its linked question records or include them in the summary.
- Solve-order/time summary handles outliers robustly with the median; records missing metadata are excluded from the summary.
- Browser smoke does not call an AI endpoint. The summary benchmark does not load/call a model.
