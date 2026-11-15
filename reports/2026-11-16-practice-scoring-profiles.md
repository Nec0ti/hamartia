# Practice scoring profiles

Status: implemented on `codex/practice-scoring-profiles` from `af7c8d48ab185739fb7fc251c449429b312b3e36`; locally verified on 2026-11-16. This extends the existing shared versioned profile catalog from Exam records to `PracticeSession` records. It does not create a second catalog or claim that user-defined profile labels reflect an official Maarif, national, or other authority rule.

## Behavior

- Each practice record stores the complete scoring-profile snapshot used at creation. Existing JSON records, profile-omitting requests, and older backups resolve to immutable `legacy-yks@1`; custom profile changes append a new version and do not rescore prior rows.
- Manual, host-approved Study Agent, and focused-timer creates bind a profile reference and persist its snapshot. An edit without a new selection preserves its existing snapshot; an explicit selection resolves the chosen catalog ID/version. Provider arguments cannot select a profile. The host-selected snapshot is present in the exact agent preview digest and is resolved again during approved create.
- Net uses exact rational profile weights, including blank points. Accuracy remains `correct / (correct + incorrect)`, so all-blank sessions have no accuracy. Practice sessions grant no XP; exam XP and score behavior remain unchanged.
- Focused timer drafts store the full snapshot and keep it through profile catalog edits, reload, completion, and retry. Before POST, the client freezes the exact duration, request fields, profile snapshot, and completion ID in the paused timer. If the freeze response is ambiguous, it reloads authoritative clock state before sending anything; retries replay the frozen request after time advances. For pre-upgrade PR31 drafts with an ID but no frozen payload, the client first looks up the deterministic `practice_focus_<UUID>` row. An exact match clears the timer; a missing row proceeds to a new frozen completion; a mismatch surfaces a bilingual review/cancel message without mutation.
- Topic summaries and trend groups are partitioned by profile ID and version, then by normalized subject/topic. Backup/restore preserves the shared profile catalog, full practice snapshots, and active timer draft. Legacy archives without those additions safely restore `legacy-yks@1` snapshots.

## Independent benchmark

`backend/benchmarks/benchmark_practice_profiles.py` mounts the profile, practice, and clock routers in an in-process FastAPI test client; it does not mount a provider route. Its independent fixture table asserts full custom-profile snapshots, literal score goldens, complete API rows and grouped summaries, unique record IDs, and timestamps inside the benchmark execution window. It covers malformed/negative rational weights, negative counts, zero-question rejection, fractional weights, all-blank behavior, profile v1/v2 isolation, omitted-edit snapshot preservation, explicit legacy fallback, host-selected agent snapshots, and full current/legacy backup round-trips.

Timer fixtures call the production `frontend/src/clock/practiceDuration.js` helper through a small Node bridge for 0, 999, 1,000, 59,999, 60,000, and 60,999 elapsed milliseconds. Its returned durations are checked against literal Python fixture pairs, then persisted through the API and compared as complete rows. The upgrade-recovery fixture creates a deterministic preexisting focus row plus an ID-only timer, calls the production `findLegacyFocusedCompletion` resolver with real API rows, compares the result to a literal complete row, and confirms clearing leaves exactly one saved record. Current and legacy archive tests compare every active timer field and the complete practice draft against explicit fixtures, including timer kind/status/elapsed time, labels, counts, date, completion ID, frozen completion payload, and full profile snapshot/default. Completion retry fixtures compare the complete returned/persisted row after the same key and reject a changed payload. Legacy restore compares every complete restored row to a separately computed legacy profile/net/accuracy oracle. The benchmark output reports `ai_included: false` and that provider routes were not mounted; these are scope descriptions, not measurements of model quality or resource use.

## Verification and limits

- Backend unittest discovery: 174/174 passed.
- Frontend tests: 36/36 passed; desktop tests: 40/40 passed.
- Frontend production build passed; Vite retains its large-chunk warning.
- `benchmark_practice_profiles.py --repeats 3` passed with 14 records and 13 profile/version/topic groups. It exercised complete current and legacy backup round-trips, all six timer boundaries, and legacy ID-only completion recovery.
- `scripts/benchmark_docs.py` passed for 17 rendered routes per locale, checking 108 evidence excerpts with no errors.
- `git diff --check` passed. No real AI/provider execution was performed.
- Browser smoke could not launch Chromium in this environment because `libglib-2.0.so.0` is unavailable. The automated UI tests/build and backend tests passed, but a live browser pass remains unverified here.

The matching English and Turkish user guides explain selection, immutable snapshots, legacy compatibility, timer behavior, and the non-official status of user-entered profiles. `README.md` lists the focused non-AI benchmark and links this report.
