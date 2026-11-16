---
name: hamartia-workflow
description: Change workflow for Hamartia's study tool across curricula, its current TYT/AYT full-mock support, local AI boundary, and benchmark process.
---

# Hamartia workflow

1. Read `AGENTS.md`, `notes.md`, `backlog.md`, and the latest record under `reports/`.
2. Inspect the API/UI points that use the change and JSON data compatibility.
3. Choose one student-visible vertical slice; complete the related backend and frontend parts together.
4. Test non-AI behavior; do not call a real local AI service.
5. Record test/benchmark commands and results in a dated report under `reports/`.
6. Commit each completed small slice; when transferring to GitHub, verify the source branch SHA, new commit SHA, and ref result.
7. For data export/restore changes, count all record types and the `uploads/` directory; exclude secret fields, fully validate the archive in staging, and preserve old data before the swap. Check restore for conflicts with the app's process lock.
8. For exam-context missed-question analysis, state the measurement denominator explicitly; do not derive an accuracy rate from only questions recorded as missed. Old question JSON must remain readable, and deleted exam links must not pollute summaries.
9. Derive topic performance measures only from completed `practice_sessions.json` records; exclude blank questions from the accuracy denominator and accept old backup archives even without the new list file.
10. A focused-session draft is stored temporarily only in the same browser profile; write completed results once to the existing practice API and do not call a real model.
11. Build topic trend charts only from saved practice sets; do not draw null accuracy as zero, and keep management actions available for sets older than the last six.
12. Do not save a provider `OpenAIError` as successful analysis; return a visible HTTP error for question analysis, test only with a fake provider exception, and keep real models outside automated verification/benchmark scope.

## Measurement rule

Net calculations, storage, APIs, UI builds, and smoke flows without model calls are in scope. Model startup, responses, quality, latency, and hardware usage are out of scope.
