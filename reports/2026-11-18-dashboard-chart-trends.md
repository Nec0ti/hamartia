# 2026-11-18 dashboard chart trends

## Change

The exam net chart now includes every recorded net, including zero and negative values, and sorts results by exam date, creation time, then ID. Added a companion positive/negative bar chart showing each net's change from the prior saved exam. The first record has no delta; fewer than two records show an explicit prompt instead of implying improvement. Both charts use the dashboard's existing subject, exam-type, and immutable scoring-profile-version filters. Added bilingual labels, explanatory copy, empty states, clearer chart colors, and a zero baseline. The performance radar's duplicate identical data layer was removed and its single series now uses the same accent color. No API, storage, or data migration change.

## Verification

- `cd frontend && npm ci` — installed locked dependencies; audit reported zero vulnerabilities.
- `cd frontend && npm test` — 56/56 passed. The focused assertions cover chronological same-day ordering, zero/negative outcomes, positive and negative deltas, empty and single-record history, and separate scoring-profile versions.
- `cd frontend && npm run build` — passed after all chart changes. Existing Vite warning remains that the main minified JS chunk exceeds the 500 KB advisory threshold.
- `HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm run test:browser` — API and Vite started, but Chromium could not launch because `libglib-2.0.so.0` is unavailable in this NixOS environment. No browser screenshot or responsive visual review was possible.
- The browser command without `HAMARTIA_PYTHON` also cannot find system FastAPI/Uvicorn; using the existing Hamartia virtualenv got as far as the Chromium launch.

## Limits

No backend tests were needed because the API and saved data are unchanged. Desktop/mobile layout, rendered chart tooltips, and accessibility still need the browser smoke on a host with Chromium's shared libraries. No AI/provider execution or benchmark was run.
