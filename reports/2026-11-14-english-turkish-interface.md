# English and Turkish application interface

## Scope

- Default the application to English and persist the English/Turkish selection in local browser storage.
- Translate the application navigation, settings, exam dashboard, question review, study plan, practice sessions, Cosmos view, validation, errors, and accessible names.
- Format numbers and dates with the selected locale while leaving stored values and user-entered subject/topic text unchanged.
- Document the language selector on the English and Turkish GitHub Pages guides.
- Do not call a local or hosted model during tests or benchmarks.

## Verification

- `cd frontend && npm test`: 15 tests passed.
- `cd frontend && npm run build`: succeeded in 32.12 seconds. The JavaScript output is 726.76 KB minified / 206.90 KB gzip; Vite reports the existing 500 KB chunk warning.
- `PYTHONPATH=backend python -m unittest discover -s backend/tests`: 81 tests passed using an isolated Python 3.14 environment with `backend/requirements.txt` installed.
- All five backend benchmarks completed with `ai_included: false`:
  - JSON exam storage, 1,000 records: append 19.4822 sec; read 0.0121 sec; single-record update 0.0428 sec; delete 0.0409 sec; document update 0.0049 sec; progression 0.0029 sec.
  - Local question flow, 100 questions: upload 0.8419 sec; list 0.0022 sec; insights 0.0025 sec; attempt 0.0069 sec; review 0.0081 sec; update 0.0097 sec; delete 0.0085 sec; text capture 0.9701 sec. Section question upload 0.4732 sec; insights 0.0078 sec.
  - Backup/restore, 50 files / 100 MiB: export 4.652 sec; validation 0.9889 sec; restore 1.2053 sec.
  - Question-order summaries: 1,000 records in 0.014425 sec; 10,000 in 0.16043 sec.
  - Topic-practice summaries: 1,000 sessions in 0.013741 sec; 10,000 in 0.082967 sec. At 10,000 sessions, write took 0.1479 sec and read 0.411784 sec.
- A source scan found 226 literal translation references and no missing dictionary keys.
- Browser smoke coverage now checks English default/fallback, persistence, localized dates and chart labels, and existing study flows in both languages. Local execution is blocked because this host lacks `libglib-2.0.so.0`; GitHub Actions must run it before merge.
- The first PR CI run found that an eagerly evaluated assertion message consumed the seed response body before JSON parsing. The smoke now reads the error body only for a failed response; the rerun is pending.
- The local GitHub Pages browser smoke has the same missing Chromium system dependency and was not verified locally. The public Pages deployment remains on the existing `master` build until this PR is merged.

## Limits

Benchmark timings are single local runs and should be compared with the same host and dataset. No AI model was started or benchmarked. Cross-platform packaging and the ChatGPT account flow are future phases.
