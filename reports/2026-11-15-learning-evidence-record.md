# User-entered learning-evidence records

## Scope

Added a separate `learning_evidence.json` collection for a student's own report of an activity completed from a Study Plan topic suggestion. Each record stores the selected subject/topic, the user's activity description and observation, the user's calendar date, optional HTTP(S) reference text, and stable ID/creation time. The API supports list/create/edit/delete with field trimming, bounded lengths, strict ISO date, and HTTP(S)-only URL validation. Existing backup ZIPs without this optional collection restore it as empty; current backups include it.

The Study Plan form is available in English and Turkish. It requires selecting a suggested topic and entering the activity and observation; users can date, optionally link, edit, and delete records. The UI describes completion as self-reported. These records do not touch review attempts, practice/exam results, or XP, and no model/provider call or inference path was added. EN/TR wiki and backup pages explain these limits.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -q` — 125 tests passed, including API validation/CRUD/isolation and current/legacy backup behavior.
- `npm test` — 26 frontend tests passed.
- `npm run build` — passed; Vite reported the existing large-bundle advisory (801.71 kB minified JS).
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) npm --prefix frontend run test:docs'` — browser smoke passed across 34 EN/TR pages, including reciprocal locale routes, section parity, internal links, 390px layout, and keyboard skip link.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) HAMARTIA_PYTHON=/home/necoti/hamartia/.venv/bin/python npm --prefix frontend run test:browser'` — passed the full local browser smoke, including the Turkish suggested-topic selection and learning-evidence create/edit/delete flow. The report asserts the persisted payload contains only evidence fields and that cleanup succeeds. Full smoke timings: navigation 6,272 ms; practice persistence 1,251 ms; focused session 6,224 ms; practice trend/history 1,952 ms; capture/review persistence 3,073 ms; exam CRUD 6,703 ms; question edit/delete 681 ms; settings 635 ms; backup download 118 ms. AI routes are excluded by explicit request assertions; the browser uses only the local app fixture.
- `python3 scripts/benchmark_docs.py` — automated offline integrity passed: 17 pages per locale, 34 navigation routes, 17 paired heading-anchor orders, 816 local links/assets, zero errors. Final rendered-wiki SHA-256: `fd2cd4f7271b6d1a2da0cf1bf7ba562b453d59506a9259d679911e0dfdeb869b`. External links were counted but not fetched; no AI or network access was used by this checker.
- `node --check frontend/_smoke.cjs`, `node --check frontend/_docs_smoke.cjs`, and `git diff --check` — passed.

## Limits

The learning-evidence entry is the student's self-report; Hamartia does not verify activity completion, open or validate references, grade reflections, or infer learning/mastery. The offline docs checker is structural and does not replace the separate human blind retrieval tasks or fixed-viewport screenshot review, which remain pending. The Playwright browser is Nix-provided because the host's bundled Chromium lacks system shared libraries. No AI/provider request or local model execution was run.
