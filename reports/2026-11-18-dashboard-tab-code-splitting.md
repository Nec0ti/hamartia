# 2026-11-18 dashboard initial-bundle reduction

## Change

Kept the default Dashboard tab eager and changed the Questions, Study Plan, Study Agent, Cosmos, Clock, and Coming Soon views to `React.lazy`. A bilingual, polite live status appears in the shared content area while a selected tab module loads. The app-level `ClockProvider` remains mounted around navigation, so the timer scheduler continues to work while the Clock tab is not mounted. Dashboard question upload still carries the selected exam into Questions.

## Bundle measurement

Built the clean `origin/master` baseline and the changed frontend with the same lockfile-pinned dependencies in the same worktree and host, using Vite 6.4.6. Values are Vite's reported minified size and gzip estimate, not a browser network trace.

| Output | Baseline | After | Change |
| --- | ---: | ---: | ---: |
| Initial JavaScript | 891.27 kB / 245.11 kB gzip | 777.06 kB / 222.59 kB gzip | −114.21 kB / −22.52 kB gzip |
| CSS | 19.25 kB / 4.54 kB gzip | 19.25 kB / 4.54 kB gzip | unchanged |

Vite emitted deferred feature chunks: Questions 20.37 kB (5.41 gzip), Study Plan 34.11 (8.76), Study Agent 35.42 (7.13), Clock 19.54 (4.98), Cosmos 4.65 (1.64), and Coming Soon 0.97 (0.47). Small shared icon chunks are also deferred. The initial chunk remains above Vite's 500 kB advisory because the dashboard still needs Recharts; splitting these tabs does not remove the dashboard chart dependency.

## Verification

- `npm test` — 54/54 passed.
- `npm run build` — passed; baseline and changed sizes recorded above.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm run test:browser'` — passed the existing full browser smoke. Added checks proved the Dashboard does not request Study Agent/Clock modules initially, selecting those tabs fetches their modules, the selected Study Plan shows an accessible bilingual loading status while its module request is held, and a Dashboard missed-question flow carries the exam subject/count into the lazy Questions tab. Smoke output reported `ai_included: false`.
- The Playwright bundled Chromium cannot start on this host because `libglib-2.0.so.0` is unavailable; the smoke passed using Nix Chromium.
- No API or persisted-data contract changed. No AI/provider call was made.

## Limits

The existing large initial chunk warning remains. This change reduces initial transfer; it does not reduce the total JavaScript users download after opening all tabs. Lazy chunk download failures still have no dedicated error-boundary retry UI.
