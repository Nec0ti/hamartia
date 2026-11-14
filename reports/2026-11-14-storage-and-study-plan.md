# Data integrity and study priorities — 2026-11-14

## Scope

- Reading and preserving malformed collection JSON.
- Concurrent exam/question updates.
- Deterministic subject/topic priority from the mistake notebook.
- Backend and frontend verification without local AI.
- Vite security patch and frontend production build.

## Changes

- `StorageService.update_list` provides read-modify-write under a lock. Exam deletion, question tag/analysis records, and study document additions use this path.
- If JSON is malformed or a record does not match the schema, reading raises `StorageError`; it is not treated as an empty list and overwritten.
- `/questions/insights` groups wrong questions by subject/topic; the topic with the most repeats comes first, with alphabetical order for ties. Error tags and the most recent record day are also returned.
- The Study Plan screen displays these results. No endpoint connects to a real model.
- Changed Vite from `^5.4.8` to `^6.4.6`. The official [GHSA-p4f5-76q4-ffq7](https://github.com/vitejs/vite/security/advisories/GHSA-p4f5-76q4-ffq7) advisory affects <=6.4.5; [6.4.6 release](https://github.com/vitejs/vite/releases) is patched.
- Added PNG/JPEG/WebP signature validation to the question file extension/MIME checks; a PNG with an incorrect header returns 415.
- Added a reviewed status for wrong questions; the plan lists only pending records, and the user can undo the status.
- User XP is the total of XP calculated per exam and the existing profile bonus; level derives from total XP, streak from exam days. Profile and Cosmos use the same XP projection.
- The AI endpoint uses an async OpenAI client that reads saved settings and adds the image to the request as a data URI. As requested by the user, this path was not tested/benchmarked; it requires verification on another computer.

## Verification

| Work | Result |
| --- | ---: |
| Backend tests | 20/20 passed |
| Frontend formatter tests | 3/3 passed |
| Frontend production build (including review status flow) | passed, 20.55 sec |
| Main JS build | 661.61 KB minified / 190.49 KB gzip |
| 100 wrong-question upload benchmark | 0.8692 sec / 115.04 records/sec |
| Listing 100 questions | 0.0017 sec |
| Priority calculation for 100 saved records | 0.0031 sec |
| Upload 100 questions after image-signature validation | 0.5873 sec / 170.28 records/sec |
| List/priority calculation in the same review test | 0.0010 sec / 0.0020 sec |
| Review-loop benchmark: upload 100 questions | 0.4798 sec / 208.43 records/sec |
| Review list / review update | 0.0031 sec / 0.0036 sec |
| Append 1,000 JSON exams | 13.6749 sec / 73.13 records/sec |
| Read 1,000 JSON exams | 0.0078 sec |
| XP/streak calculation for 1,000 exams | 0.0017 sec |
| `npm audit --offline` | 0 findings in cache |

AI-free benchmark commands:

```sh
python backend/benchmarks/benchmark_storage.py
python backend/benchmarks/benchmark_questions.py
```

Frontend verification commands:

```sh
npm test
npm run build
```

## Limitations

- Python tests used the system Python 3.14/Nix FastAPI and Pydantic packages; missing `openai` and `python_multipart` imports were stubbed in the test harness. The model was not loaded or called.
- Frontend dependencies were installed with `npm ci --offline --ignore-scripts`. Install scripts were not run in the sandbox environment; Vite build and tests still passed.
- `npm audit --offline` represents only the local npm cache, not a current internet audit.
- The image header is validated, but the pixel stream is not decoded; a malformed file with a matching signature may be accepted.
- JSON append rewrites the entire file each time. The 1,000-record measurement shows this cost; SQLite is needed for concurrent processes/multiple workers or growing histories.
- The bundle exceeds the 500 KB threshold. Code splitting was not done in this work slice.
- GitHub Actions frontend/backend jobs completed successfully for `feat: add a local mistake review loop`, review undo, and later docs commits. The XP/streak derived-summary workflow is currently running. Browser end-to-end flow was not run.
- The local `git write-tree` and GitHub progress branch tree SHA matched at `55fcba2eb952846ef60936e6bf9bb978daf132c6`; source `master` remained at `c5642d0`.

## Model boundary

None of the checks and benchmarks in this report include a model call. Local AI hardware, model, prompt, and response-quality measurements must be performed separately on another computer.

## 2026-11-14 Cosmos view

- `CosmosTab` now displays level/XP/streak and up to nine pending topic orbits from `/user` and `/questions/insights` GET endpoints. Data is derived locally; the screen does not write Cosmos or user data and does not call AI.
- Frontend tests passed 4/4; XP progress bounds and the level threshold were asserted. `npm run build` passed in 17.64 sec.
- Production bundle: 668.34 KB minified / 191.82 KB gzip. The 500 KB warning remains.
- Shared XP bar helpers were aligned with the backend formula so the first-level target is 500 XP; the navbar and Cosmos use the same calculation.
- `chromium`, `firefox`, Playwright, and Puppeteer were unavailable in this environment, so browser smoke/screen reader checks were not run. Accessible progress bar semantics were checked at build and source level.
- The Cosmos assault API was not connected to the screen: XP and Cosmos JSON are written separately, with a risk of inconsistency/loss in concurrent calls; a failed assault also does not implement the expected stake/refund flow. A separate backend task and tests are required first.
- GitHub Actions successfully completed frontend test/build, backend unittest, and both AI-free benchmark steps for the last code commit `0c72061` and the following documentation commit (run `43603845596`). The workflow does not call the model service.
