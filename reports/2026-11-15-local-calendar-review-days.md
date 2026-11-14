# User calendar days for review activity

## Change

Review scheduling previously took the UTC date from `attempted_at`, while the packaged API compared it with its host's `date.today()`. Around midnight, a saved answer could be treated as tomorrow's activity or immediately due. The UI also received Turkish missing-subject/topic strings directly from the backend.

New browser attempts now send an immutable `attempt_day` in `YYYY-MM-DD` form alongside the existing UTC instant. The API validates the optional date and persists it in the `ReviewAttempt`; if an older API client omits it, the API stores the UTC date from its UTC timestamp. `/questions/insights` accepts an optional `today` date; the browser always sends its current local calendar day. Legacy stored attempts without `attempt_day` keep the previous UTC-date interpretation because their original local day cannot be recovered. New dates do not depend on a server timezone, and future date conversion is not inferred from an offset.

Missing subject/topic identifiers remain empty in API and persisted data. Study Plan and Cosmos render English or Turkish fallback labels at the UI boundary. An unclassified topic shows localized guidance instead of offering a focused session that would fail server validation; translated fallback labels are never persisted. Backup export/restore preserves the new attempt field without a migration or rewrite of existing data.

## Verification

No ChatGPT or local AI provider was called.

- Backend unit suite: 98/98 passed, including positive/negative UTC-offset and midnight boundaries, deterministic legacy fallback, API date validation, blank label identifiers, and backup restore round-trip.
- Frontend unit suite: 18/18 passed, including UTC+ and UTC− date serialization and language-specific missing-label fallback.
- Vite production build passed. Existing bundle-size warning remains (>500 kB; this build's main JS is 743.63 kB minified / 211.15 kB gzip).
- Mocked browser smoke passed. It verifies attempt-day request/persistence across reload, explicit `today` query, missing labels in English and Turkish on both Study Plan and Cosmos, disabled focus for unclassified topics, and the valid focused-session flow. Reported `ai_included: false`.
- All six AI-free benchmarks passed with seed `20261114`. The mixed workload benchmark's independent oracle covers same-day activity and review due/scheduled counts. It used 1,500 exams, 2,500 questions, and 4,000 practice sessions; question-insights warm p50 was 0.149839 seconds. The other benchmark oracles also passed for storage, question CRUD, backup, question order, and practice sessions.
- `git diff --check` passed.

Commands used:

```sh
PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python -m unittest discover -s backend/tests -v
cd frontend && npm test && npm run build
cd frontend && HAMARTIA_PYTHON=/tmp/hamartia-siwc-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser
PYTHONPATH=backend /tmp/hamartia-siwc-venv/bin/python backend/benchmarks/<benchmark>.py --json-output /tmp/hamartia-calendar-<benchmark>.json
```

The six benchmark commands ran sequentially. Their outputs were written under `/tmp`, not into the repository.

## Limits

Historical records cannot recover the calendar date that was visible to the user at the time; they retain UTC semantics. New browser attempts preserve the actual local date supplied when the user answers. Consumers using the API without a `today` query continue to use the packaged API process's local day. Real model or account behavior is outside this patch and was not exercised.
