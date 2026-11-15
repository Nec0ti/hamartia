# Practice scoring profiles

Status: implemented on `codex/practice-scoring-profiles` from `af7c8d48ab185739fb7fc251c449429b312b3e36`; locally verified on 2026-11-16. This extends the existing shared versioned profile catalog from Exam records to `PracticeSession` records. It does not create a second catalog or claim that user-defined profile labels reflect an official Maarif, national, or other authority rule.

## Behavior

- Each practice record stores the complete scoring-profile snapshot used at creation. Existing JSON records, profile-omitting requests, and older backups resolve to immutable `legacy-yks@1`; custom profile changes append a new version and do not rescore prior rows.
- Manual, host-approved Study Agent, and focused-timer creates bind a profile reference and persist its snapshot. An edit without a new selection preserves its existing snapshot; an explicit selection resolves the chosen catalog ID/version. Provider arguments cannot select a profile. The host-selected snapshot is present in the exact agent preview digest and is resolved again during approved create.
- Net uses exact rational profile weights, including blank points. Accuracy remains `correct / (correct + incorrect)`, so all-blank sessions have no accuracy. Practice sessions grant no XP; exam XP and score behavior remain unchanged.
- Focused timer drafts store the full snapshot and keep it through profile catalog edits, reload, completion, and retry. Completion is idempotent for the same key and content; a conflicting body with that key is rejected.
- Topic summaries and trend groups are partitioned by profile ID and version, then by normalized subject/topic. Backup/restore preserves the shared profile catalog, full practice snapshots, and active timer draft. Legacy archives without those additions safely restore `legacy-yks@1` snapshots.

## Independent benchmark

`backend/benchmarks/benchmark_practice_profiles.py` mounts the profile, practice, and clock routers in an in-process FastAPI test client; it does not mount a provider route. Its independent fixture table asserts full custom-profile snapshots, literal score goldens, complete API rows and grouped summaries, unique record IDs, and timestamps inside the benchmark execution window. It covers malformed/negative rational weights, negative counts, zero-question rejection, fractional weights, all-blank behavior, profile v1/v2 isolation, omitted-edit snapshot preservation, explicit legacy fallback, host-selected agent snapshots, and full current/legacy backup round-trips.

Timer fixtures cover 0, 999, 1,000, 59,999, 60,000, and 60,999 elapsed milliseconds with expected second truncation and minute carry. Completion retry fixtures compare the complete returned/persisted row after the same key and reject a changed payload. Legacy restore compares every complete restored row to a separately computed legacy profile/net/accuracy oracle. The benchmark output reports `ai_included: false` and that provider routes were not mounted; these are scope descriptions, not measurements of model quality or resource use.

## Verification and limits

- Backend unittest discovery: 174/174 passed.
- Frontend tests: 32/32 passed; desktop tests: 40/40 passed.
- Frontend production build passed; Vite retains its large-chunk warning.
- `benchmark_practice_profiles.py --repeats 3` passed with 13 records and 12 profile/version/topic groups. It exercised complete current and legacy backup round-trips and all six timer boundaries.
- `scripts/benchmark_docs.py` passed for 17 rendered routes per locale, checking 108 evidence excerpts with no errors.
- `git diff --check` passed. No real AI/provider execution was performed.
- Browser smoke could not launch Chromium in this environment because `libglib-2.0.so.0` is unavailable. The automated UI tests/build and backend tests passed, but a live browser pass remains unverified here.

The matching English and Turkish user guides explain selection, immutable snapshots, legacy compatibility, timer behavior, and the non-official status of user-entered profiles. `README.md` lists the focused non-AI benchmark and links this report.
