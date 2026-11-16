# Remote social prototype cancellation

Based on current `master` `eec83875489d2731ec12fd12aa42aaa4acb3f2d3`, this change removes Google/Firebase sign-in, remote profiles and forum UI, the separate API/PostgreSQL service and migrations, moderator/quota code, agreement drafts, and their dependencies, tests, benchmarks, CI, and active setup/legal documentation. No direct-message feature was implemented. Old release entries and implementation reports remain dated historical records; they are not current launch requirements.

The local student profile, onboarding/editor, XP levels, and avatar cosmetics remain. Study records stay in local app storage and backups; Study Agent requests continue to use ChatGPT by default or a configured OpenAI-compatible endpoint, including a local endpoint, only after the user's per-request approval. No existing user data, secrets, or remote database were inspected, changed, or deleted; no server or provider was contacted.

## Verification

- Frontend unit tests: 54/54; desktop tests: 56/56.
- Backend suite: 289 run, 288 passed, one Windows-only test skipped.
- `benchmark_student_profile.py --repeats 3`: passed; `ai_included: false`, 25 full-row oracles, 24 competing updates, backup/reset round trips, and zero provider/network tripwire calls.
- Frontend production build and release metadata tests passed. The build retains its existing large-chunk warning.
- Offline documentation integrity benchmark passed: 17 rendered routes per locale, 816 local links/assets, 156 exact evidence excerpts, no errors, no network, and `ai_included: false`.
- Browser documentation/onboarding smokes could not launch locally: Chromium requires missing `libglib-2.0.so.0`. Pull-request CI is still needed for browser and Windows/Linux package checks.

No model execution or AI benchmark was run. The profile benchmark measures local persistence and unlock boundaries only.
