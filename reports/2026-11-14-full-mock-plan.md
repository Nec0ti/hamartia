# Plan for subject-level results in a TYT/AYT session

## User need and current gap

The project note in Second Brain and the source conversation describe a need to save all mock-exam results, not just paragraph questions, with duration/correct/incorrect/blank counts. The repository's `Exam` record still has only one `subject` and one group of counts. As a result, a full TYT/AYT mock is either entered as if it were one subject or split into multiple records, which distorts session/net/XP counts.

## Goal

Keep a full TYT/AYT mock in one record and attach the user's subject results to that exam. Derive total correct/incorrect/blank counts and net from the subjects, enter duration as the total session duration, and calculate XP/streak/exam count once per session. Keep branch exams as the current single-subject entry. Allow free-text subject names; do not hard-code the official test list.

## Planned data contract

- `Exam.sections` is a new backward-compatible list; use `[]` as the default for old records and archives.
- Each `ExamSection` has a trimmed, non-empty subject name and correct/incorrect/blank counts of zero or greater.
- Section names are unique case-insensitively within a session; a sectioned exam has at least one section.
- When a TYT/AYT exam has a section list, its top-level `subject` is `TYT General`/`AYT General`; correct/incorrect/blank totals are derived by the backend from the section totals. Duration remains in the existing single-session field. XP is calculated once from this aggregate.
- Branch records continue with `sections=[]` and their existing fields. Old TYT/AYT records without sections remain readable and editable.
- When a wrong question is added for a section, its existing `Question.subject` is the section name; the API validates question number/solve-order bounds against that section's size and stores an `exam_section_total` snapshot. This field remains empty for old/branch questions. Solve-order insights are calculated by section name and snapshot size.

## Areas affected

- Backend schema/API: `ExamSection`, derived totals/validation, exam create/update, section-linked wrong-question validation.
- Calculations: progression counts a session once; dashboard keeps one session count and uses that section's net when a subject is selected.
- UI: `AddExamModal` keeps the branch path and adds subject result rows for TYT/AYT. `RecentExams` opens subject details on the single session row; each subject has its own wrong-question context. `TrendChart` plots the selected subject's section results.
- Backup: export/restore with the `Exam` schema must continue reading existing JSON lists and old archives; new section fields must round-trip.
- Verification: backend CRUD/limit/legacy/backup regressions, frontend test/build, browser create → reload → edit → delete, section-linked wrong question and trend. No AI route calls.
- Benchmark: measure creation/update/listing of multi-section sessions and section trend projection separately with an AI-free script; rerun existing storage/question/backup/practice benchmarks.

## Data and behavior risks

- No live `backend/data` sample exists in the repo; actual user JSON cannot be checked here. Backward compatibility will be evidenced by legacy fixtures and old backups.
- Use one total XP policy; do not turn sections into separate exam records and multiply XP.
- Snapshot section size in `Question.exam_section_total` so renaming a section does not change the solve-order group for previously linked wrong questions. `Question.subject` is already the subject name and also stores this context.
- Free-text section names can make spelling variants appear as multiple subjects; the user must keep displayed names consistent manually. A standard subject catalog is out of scope.

## Sequence

1. Commit the plan/backlog.
2. Commit the backward-compatible schema and backend API/test changes.
3. Commit UI and section filter/trend/test changes.
4. Commit browser smoke and AI-free benchmark changes.
5. Update all reports/notes/backlog; transfer each local commit separately through the GitHub API using the same tree SHA and verify Actions completion.
