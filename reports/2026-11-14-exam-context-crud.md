# Exam type and history management — 2026-11-14

## Scope

- Save an exam as TYT, AYT, or branch; read old JSON records without data loss.
- Keep the type filter separate from the subject filter and apply the selected type to exam totals and trends.
- Edit or confirm deletion of records in exam history.
- Run the real API and UI flow using temporary local data; verify that no AI routes are called.

## Data and API behavior

- Allowed values for `Exam.exam_type` are `tyt`, `ayt`, and `branch`; old JSON records with no type are treated as `branch`. No file migration is needed.
- `PUT /exams/{id}` uses locked `update_list`; it changes type and result fields while preserving `id` and `created_at`. Returns 404 if the record is not found.
- `DELETE /exams/{id}` uses the same locked mutation pattern; returns 404 if the record is not found.
- The dashboard narrows the exam count, average net, trend, and table using the TYT/AYT/branch filter. The XP profile continues to derive from all exam history.
- All exams are listed in date order; each row provides edit and confirmed-delete buttons.
- Browser smoke updates a created AYT exam to TYT with a new subject name, confirms and deletes it, then verifies the temporary `exams.json` file is empty.

## Verification

| Check | Result |
| --- | ---: |
| Backend unittest | 32/32 passed |
| Frontend Node tests | 4/4 passed |
| Frontend production build | 20.77 sec, succeeded |
| Main JS bundle | 676.80 KB minified / 193.58 KB gzip |
| Online `npm audit` | 0 findings |
| Chromium smoke navigation / capture+review / exam CRUD | 2.266 / 3.483 / 1.039 sec |
| 1,000-record JSON append / read | 19.178 sec / 0.0078 sec |
| Single-record update / delete | 0.0272 sec / 0.0237 sec |
| Progression calculation for 1,000 records | 0.0017 sec |
| 100 image-question records | 0.3149 sec / 317.57 records/sec |
| 100 text-only question records | 0.4523 sec / 221.11 records/sec |

Commands:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
cd frontend && npm test && npm run build && npm audit
cd frontend && npm run test:browser
```

## Issues found and fixed

- Browser smoke showed that the actual dashboard called `api.user.get()`, but the default API object did not export `user`. The default export was fixed, and smoke asserts that this error does not occur on initial load.
- The profile badge pushed the navbar beyond 390 px on narrow screens. The brand text and XP bar are hidden on small screens while the navigation icons remain.
- The empty default radar produced a duplicate tick key and a NaN SVG line because it used a numeric `PolarAngleAxis` and duplicate `PolarRadiusAxis`. This was fixed with a categorical axis and a single radius axis.

## Limitations

- Since the actual exam type is not present in old records' JSON, they default to branch; the user can change this type by editing the record.
- Statistics depend on the selected type and subject filters. The XP total intentionally remains unfiltered.
- Browser smoke checks CRUD and persistence with a sample record; real user data volume has not been benchmarked for very large histories.
- Local AI was not loaded, called, or benchmarked. Multimodal endpoint verification on another computer is pending.
- The production JS bundle exceeds the 500 KB recommended threshold; the current build succeeds, but the Vite warning remains.
- GitHub Actions run `43608878405` (#41) successfully completed frontend test/build/browser smoke and both backend test and benchmark steps for the same source code.
