# Versioned exam scoring profiles

Status: implemented and locally verified on 2026-11-15. This first slice scopes custom scoring to exam records (TYT/AYT full mocks and branch exams). It does not generalize scoring across the whole app: focused `PracticeSession` records and their topic trends still use the legacy YKS quarter-penalty formula. Profile-aware practice sets, focused-timer completion/idempotency, editing, and backup remain open in [backlog.md](../backlog.md).

## Behavior

- Existing and profile-omitting exam records resolve to immutable `legacy-yks@1` snapshots. That policy remains one point per correct answer, a one-quarter point penalty per wrong answer, and zero for blanks.
- Students can create custom profiles with a display name, country label, and nonnegative exact rational points for correct, incorrect, and blank answers. Editing appends a version. Saved exams retain the exact rule snapshot used when recorded, even if the profile changes later.
- Exam Dashboard totals, history, subject summaries, and trends filter by exact profile ID and version. Section totals are aggregated before applying the saved rule.
- XP retains the existing legacy raw-count activity formula across every exam profile. Equal raw counts and duration produce equal XP regardless of score weights; XP is progression, not mastery evidence.
- Backup/restore includes the custom profile catalog; older backups and JSON records without the new fields default to legacy YKS.
- Profile labels are user-entered. No official exam profile, national authority approval, or Maarif alignment is claimed.

## Correctness checks

Hand-authored goldens for identical counts (12 correct, 4 incorrect, 4 blank; 30 minutes):

| Profile rule | Net | XP |
| --- | ---: | ---: |
| Legacy YKS: 1, −1/4, 0 | 11 | 168 |
| Custom: 1, 0, 0 | 12 | 168 |
| Custom: 1, −1/2, 0 | 10 | 168 |

A two-section full mock with counts (4,1,1) and (8,3,3), using correct=1/3, wrong penalty=1/6, blank=1/12, aggregates to `(4+8)/3 − (1+3)/6 + (1+3)/12 = 11/3`. The API request deliberately supplies incorrect root subject/count totals; the service derives totals from the exact persisted section names and counts. The benchmark appends a no-penalty profile v2 with a full wrong-answer penalty: the prior exam remains catalog-resolvable as v1 at net 12, and the new v2 exam scores 8. POST and persisted GET results are compared as complete records, including XP, IDs, timestamps, sections, and snapshot/rule. Global `/user` and `/cosmos` endpoints report 843 XP / level 2 across nine exams. A full expected row corrupted by 0.25 net is rejected outside the timed section. A simulated pre-profile ZIP with `exam_profiles.json` and exam snapshots removed restores with legacy YKS defaults and net 11.

Boundary vectors also include the reviewed counterexample: correct=1, wrong=0, blank=1 with four blanks scores net 4 and XP 0; the Dashboard average includes that exam. A rule with relatively prime denominators 3, 5, and 7 uses counts (2,3,4) and yields literal net 67/105 with XP 3. Wrong-only (0,5,0) under the half-penalty rule yields −2.5 net and 0 XP; the zero-question vector yields 0/0. Nine API-created exam IDs must all be unique. Backup restore compares every full exam row and every custom profile version to independent expected vectors.

## Local verification

- Backend suite: 131 tests passed.
- Focused profile tests: 6 passed, including exact-rational validation, section aggregation, legacy updates, immutable profile versions, equal XP, and backup/restore.
- Frontend unit suite: 31 tests passed, including profile filter isolation, snapshot rule previews, the three score goldens, the all-blank positive-score average, and EN/TR translations.
- Frontend production build: passed. Vite reported the existing large-bundle warning (813.44 kB minified JS); no build error.
- `backend/benchmarks/benchmark_exam_profiles.py --repeats 3`: passed. Persisted GET `/exams` p50 was 0.006374 s and p95 0.007863 s on Python 3.14.8, Linux x86_64; these are local reference measurements, not cross-machine thresholds. The workload has fixed hand-authored inputs, not a seeded random generator; generated UUIDs are opaque IDs used only to partition exact profile versions.
- Backend CI now runs `benchmark_exam_profiles.py --repeats 3` alongside the existing non-AI benchmark suite.
- `scripts/benchmark_docs.py`: passed integrity checks for 17 pages in each locale, 816 local links/assets, 106 evidence excerpts, and bilingual navigation/anchor parity. Human retrieval/usability sessions and screenshot runs remain pending; no sealed blind test or human result is claimed.
- Browser smoke passed using the repository Playwright runner with Nix Chromium and the backend virtual environment. Its Turkish UI flow creates a custom half-penalty v1, saves a sectioned exam at net 10, separates it from a legacy net-11 record in the Dashboard filter, edits the profile to v2, confirms the v1 score stays 10, saves a v2 exam at net 8, and verifies v1/v2 filters each show only their own version. It also creates the exact all-blank blank-credit case and verifies both the net 4 history row and Dashboard average. The smoke output is `study_plan_and_local_crud_browser_smoke` with `ai_included: false`.
- AI/provider calls: none. Benchmark requests use an in-process FastAPI TestClient and temporary directories only.

## Limits

There is no built-in catalog of official non-YKS scoring profiles. The custom rule editor accepts nonnegative exact rationals and labels only; it does not validate a profile against an authority or decide the exam format/session structure. Question/practice trends are still distinct from exam profiles.
