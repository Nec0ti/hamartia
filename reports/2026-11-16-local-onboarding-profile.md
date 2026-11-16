# Local first-run onboarding and student profile

Date: 2026-11-16
Scope: bilingual first-run language choice and walkthrough, optional editable local student profile, safe local persistence and backup compatibility. No account, network service, or provider flow was added.

## Behavior and data boundary

- A fresh install opens the language choice in English by default, then shows four English or Turkish walkthrough cards. Students can go back, skip, or close the walkthrough; it can be replayed from Settings. After the walkthrough, an optional survey can be completed or skipped. Completing or skipping it allows normal app use.
- The survey asks for optional nickname, age in whole years, grade/year, free-form curriculum label, study preferences, study goals, and a built-in avatar. A nickname need not be a real name. No birth date or gender field exists. Empty answers remain empty; no school, curriculum, goal, age, or avatar is inferred.
- Settings opens the editor. Profile deletion has an explicit confirmation and clears the profile, resets first-run completion, and restarts welcome setup. A local document revision rejects stale saves with HTTP 409; reset increments the revision so a pre-reset editor cannot restore a deleted profile with a stale draft.
- The profile is stored in `onboarding.json` through the existing atomic, per-data-directory storage lock. It is included in manual ZIP backups. The member is optional in backup v1, so older archives restore a blank profile with revision zero. A malformed present file fails closed and is not overwritten.
- No profile field is added to social requests, Study Agent context/provider calls, question-analysis requests, or any automatic network request. Curriculum labels are user-entered; the app does not assert official alignment. Future Study Agent personalization needs separate explicit request consent and a privacy disclosure.
- The walkthrough uses the existing focus-trapped modal without animated transitions. Smoke coverage checks keyboard entry remains active across rerenders and focus moves to the next-step control when the first walkthrough card opens.

## Verification

- Focused backend profile/API/backup tests: 5/5 passed, covering empty local defaults, edit/reset/restart, strict fields and bounds, malformed on-disk fail-closed behavior, stale revision conflict, one-winner concurrent updates, current backup round trip, and legacy backup defaulting.
- Full backend suite: 298 tests run, 289 passed, 9 PostgreSQL integration tests skipped locally because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` was unset.
- Frontend unit suite: 68/68 passed. Production build passed with the pre-existing large-chunk warning.
- Desktop mock suite: 73/73 passed after a clean desktop dependency install. PyInstaller built the Linux backend sidecar successfully.
- Real-app Playwright onboarding smoke passed in Nix Chromium with synthetic values. It checked English default, completion of the four-step tour, invalid-age rejection, all survey values and avatar persistence, Settings replay/skip/edit/delete/restart, Turkish language selection and translated skip flow, backend state after reset, keyboard typing and next-step focus, zero non-local requests, and no social or Study Agent calls.
- Existing app browser smoke passed the exam history, question capture/review, practice timer, settings/key management, and backup download flows with `ai_included: false`.
- Existing bilingual docs browser smoke passed for 34 pages, reciprocal locale routes, section parity, internal links, 390 px layout, and keyboard skip link. The docs generator compiled and regenerated the EN/TR Getting Started and Privacy pages, including assertions for first-run steps and profile privacy boundaries.
- Offline docs integrity benchmark passed: 17 routes per locale, 818 local links/assets, 108 evidence excerpts, zero errors, no network access, and `ai_included: false`.
- Host-only benchmark `benchmark_student_profile.py --repeats 3` passed with 25 exact full-row oracle checks (the benchmark counts successful comparator calls), 24 same-revision updates (one accepted, 23 stale conflicts), malformed/stale/post-reset stale rejection, backup/restore/reset checks, zero provider tripwire calls, zero network tripwire calls, and `ai_included: false`. Measurements:

| Operation | p50 | p95 |
|---|---:|---:|
| Save | 0.011057 s | 0.012965 s |
| Read | 0.002754 s | 0.005563 s |
| Update | 0.009379 s | 0.009436 s |
| Backup | 0.005226 s | 0.007137 s |
| Reset | 0.007354 s | 0.008966 s |

These are local TestClient + temporary JSON filesystem measurements, not production performance claims. No local model or AI/provider execution was run.

## Limits

The browser test uses a temporary local data directory and synthetic values; it does not verify packaged-device usability or accessibility with assistive technology. Nine PostgreSQL integration tests require the CI PostgreSQL 17 service. No separate physical-device install or persistence test was run.
