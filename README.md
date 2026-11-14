# Hamartia

A local workspace that stores YKS practice exams and missed questions on this computer, and derives study priorities from recorded review attempts. Hamartia is an original application; it does not use content from external platforms.

## Documentation

The English and Turkish user guide is published on [GitHub Pages](https://nec0ti.github.io/hamartia/).

## Run locally

Python 3.12 and Node.js 22 are required. For the initial setup:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci
```

For daily use, open one terminal at the repository root:

```sh
.venv/bin/python scripts/dev.py
```

The launcher checks that the API is ready and stops both processes together; press Ctrl+C to stop it. The UI is at `http://127.0.0.1:5173`, and the API documentation is at `http://127.0.0.1:8000/docs`. If another app is using 5173, choose an available port with `HAMARTIA_FRONTEND_PORT=5174 .venv/bin/python scripts/dev.py`.

Exams, missed questions, and settings are stored under `backend/data/`. Question images are in that directory's `uploads/` folder. You can download a ZIP backup from Settings. The backup does not contain the personal API key; restoring preserves the key on the current computer.

A full TYT/AYT practice exam is saved as one session, with correct/incorrect/blank counts entered per subject; total net and XP are calculated once. History and trend subject filters show the selected section's net score. When adding a missed question from a section, the question number and solve order are limited by that section's question count. Branch exams remain single-subject.

Close the app before restoring, and run this from the repository root:

```sh
.venv/bin/python scripts/restore_backup.py hamartia-backup.zip
```

Restore validates the full archive and record schemas, then preserves the current `backend/data/` directory as `backend/data.before-restore-.../`. On Windows, use `.venv\\Scripts\\python.exe`. The operation is safely rejected while Hamartia is running.

## Local AI connection

AI is not run in tests or benchmarks. Question-image analysis is designed to connect to an OpenAI-compatible chat-completions server on another computer. In the app's Settings, enter the server address, the model name expected by the server, and the key. The default address on the same computer is `http://localhost:4000/v1`; for another computer, use its address and port on a trusted local network. The connected model must accept image content. The API key is not shown in API responses; leaving the field empty preserves the current key, and you can remove it with the explicit option in Settings.

Question text and image bytes are sent to the server shown in Settings. Do not use an endpoint exposed to the internet or one you do not trust. The connection and model response have not yet been verified on another computer.

For manual verification on another computer, save the server address/model/key; then choose **Review with Local AI** for a text question, followed by the same action on a question with an image. On success, the Council result is saved. An endpoint/model error produces a visible error and leaves the current question label/analysis unchanged. This manual flow is not run by automated tests or benchmarks.

## Non-AI verification

Backend tests from the repository root:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
PYTHONPATH=backend python backend/benchmarks/benchmark_storage.py
PYTHONPATH=backend python backend/benchmarks/benchmark_questions.py
PYTHONPATH=backend python backend/benchmarks/benchmark_backup.py
PYTHONPATH=backend python backend/benchmarks/benchmark_question_order.py
PYTHONPATH=backend python backend/benchmarks/benchmark_practice_sessions.py
PYTHONPATH=backend python backend/benchmarks/benchmark_mixed_workloads.py
```

Frontend:

```sh
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

The browser smoke test uses the `scripts/dev.py` launcher to start real FastAPI and Vite servers with a temporary data directory. It checks missed-question/exam CRUD and review flows; TYT/AYT section create/edit, reload, and capture-missed-question flows; topic net/accuracy charts and full history management; the focused-session counter/pause/reload/complete loop; and backup download. Python backend dependencies must be installed for the test; use the active virtual environment or set `HAMARTIA_PYTHON` to the Python executable path.

These commands do not load a model or send requests to a model endpoint. GitHub Actions runs frontend test/build/browser smoke and backend test/benchmark workflows.
