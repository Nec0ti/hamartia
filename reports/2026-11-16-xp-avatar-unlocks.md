# XP avatar cosmetics

Date: 2026-11-16
Scope: optional local student-profile avatar presets unlocked from the existing XP level ladder. No XP is spent, no streak is required, the eight existing presets remain available at all times, and the feature adds no profile requirement or account/network behavior.

## Behavior and boundaries

- `comet` unlocks at level 2 (500 XP), `planet` at level 3 (1,000 XP), and `galaxy` at level 5 (2,000 XP). These use the existing 500-XP-per-level progression rules.
- The English and Turkish profile editors show accessible names and the required level, and disable locked choices. The onboarding and Settings editor use the local `/user` progression result.
- The local `/student-profile` save endpoint independently enforces the same thresholds using the existing progression summary over exam XP plus the existing XP bonus. Free built-in choices and `null` remain unaffected. Social profile schemas and requests are unchanged.
- Student profile persistence and backup schemas strictly allow only built-in names. Older profile names remain valid; missing onboarding data in legacy backups still defaults to an empty profile. The new presets round-trip through backup/restore.
- The student profile and local-study XP remain absent from social requests, Study Agent context/provider requests, and question-analysis requests.

## Verification

- Focused student-profile backend tests: 6/6 passed. Coverage includes below/at all three XP boundaries, free presets at zero XP, invalid avatar rejection, persistence/reset, current backup round trips for legacy and unlockable presets, and legacy backup defaults.
- Full backend suite: 313 tests passed; 12 PostgreSQL integration tests were skipped because the local PostgreSQL test service is not configured.
- Frontend unit suite: 70/70 passed, including all unlock boundaries and both-language translation completeness.
- Frontend production build passed with the existing large-chunk warning.
- Onboarding browser smoke was attempted. The app/server started, but Chromium could not launch because this host lacks `libglib-2.0.so.0`; the bilingual disabled-state smoke assertions remain for CI.
- The persisted profile benchmark (`benchmark_student_profile.py --repeats 3`) passed with 25 full-row oracles, `ai_included: false`, zero provider-tripwire calls, zero network-tripwire calls, and exact avatar boundary checks at 500/1,000/2,000 XP. These are local temporary-filesystem measurements, not production performance claims.
- Offline documentation integrity passed for 17 routes per language, 818 local links/assets, and zero errors; the checked render hash is recorded in `reports/2026-11-15-docs-benchmark-results.json`.
- Human documentation retrieval tasks and physical Windows/Debian install/persistence checks were NOT RUN; no separate device or human test group was available.
- CI, package-install/launch checks, and independent review are pending for the PR. This change must remain unmerged until the parent coordinates the sequential ARETE release.
