# 2026-11-18 dashboard chart trends

## Change

The exam net chart now includes every recorded net, including zero and negative values, and sorts results by exam date, creation time, then ID. Added a companion positive/negative bar chart showing each net's change from the prior saved exam. Same-day records receive localized sequence labels on both axes and tooltips. Each chart has an associated screen-reader-accessible table with date, subject, net, and change for every filtered exam. The first record has no delta; fewer than two records show an explicit prompt instead of implying improvement. Both charts use the dashboard's existing subject, exam-type, and immutable scoring-profile-version filters. Added bilingual labels, explanatory copy, empty states, clearer chart colors, and a zero baseline. The performance radar's duplicate identical data layer was removed and its single series now uses the same accent color. No API, storage, or data migration change.

## Verification

- `cd frontend && npm ci` — installed locked dependencies; audit reported zero vulnerabilities.
- `cd frontend && npm test` — 58/58 passed. Focused assertions cover chronological same-day ordering and EN/TR sequence labels, accessible table row content for date/subject/net/change, zero/negative outcomes, positive and negative deltas, empty and single-record history, and separate scoring-profile versions.
- `cd frontend && npm run build` — passed after all chart changes. Existing Vite warning remains that the main minified JS chunk exceeds the 500 KB advisory threshold.
- `cd frontend && node --check _smoke.cjs` — passed. Browser smoke now scopes the fixture-date assertion to the labeled Exam history table and checks both EN/TR chart-summary tables, including each single-row/no-previous-exam state.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm run test:browser'` — passed the full browser smoke, including EN/TR accessible table names, fixture date/value rows, profile-version filtering, and the localized single-record state. Output reports `ai_included: false`.
- The default cached Playwright Chromium cannot launch because `libglib-2.0.so.0` is unavailable in this NixOS environment; the Nix Chromium override resolves it. Earlier CI runs exposed unscoped history row/cell selectors after adding the hidden chart tables; Dashboard history selectors now use `#exam-history-table`, while chart-summary assertions use their own IDs. The final-head GitHub frontend, backend, Windows recovery, and Windows/Linux package checks all passed.
- `npm run test:browser` without `HAMARTIA_PYTHON` cannot find system FastAPI/Uvicorn; the existing Hamartia virtualenv is required here.

## Limits

No direct local backend test was needed because the API and saved data are unchanged; the GitHub backend check passed. No screenshot artifact or separate human visual review was produced. No AI/provider execution or benchmark was run.
