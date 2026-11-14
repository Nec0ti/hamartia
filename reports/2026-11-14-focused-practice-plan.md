# 2026-11-14 focused topic study session — plan

## Goal

Instead of leaving the student to enter only completed sets, let them begin studying the priority topic from the Study Plan using their own materials. No external question bank or platform content will be added.

## Flow

1. Select “Study with focus” from the priority card; the subject/topic are prefilled when the session opens.
2. When the session starts, show elapsed time and correct/incorrect/blank counters. Counters cannot go below zero; the session can be paused and resumed.
3. Store the active draft in the browser's `localStorage`; after a page refresh, resume the session and timer.
4. Require at least one question result to finish. Convert the session duration to minutes+seconds and save it once using the existing `POST /practice` schema; update existing topic summaries.

## Limits and risks

- No new backend model or API is needed; a completed record is included in the existing `practice_sessions.json` and ZIP backup.
- An incomplete draft is stored only in the same browser profile and is not included in the ZIP backup. If browser data is deleted, the active session cannot be recovered.
- Hamartia does not provide questions or answers; the student solves questions from their own materials and marks the result.
- No AI endpoint is used.

## Verification

- Timer start, pause, resume, and elapsed time after refresh.
- Correct/incorrect/blank counters and prevention of values below zero.
- Reject saving with zero results; completion produces one record and appears in the topic summary.
- Chromium smoke, frontend test/build, backend regression, and AI-free benchmarks.
