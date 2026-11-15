# Study Agent Evidence Tool Loop

## Scope and data flow

The PracticeSession flow now exposes one evidence-only `hamartia_practice_prepare` function to both the ChatGPT Responses transport and the configured Chat Completions transport. The provider can submit only field names and exact quote hints. The desktop/backend host supplies the actual student transcript and saved language, validates quote provenance and field meaning with the shared deterministic resolver, then returns only verified preview values, evidence, and localized clarification questions.

The ChatGPT SIWC request carries the strict function definition as an `input` item with `type: additional_tools` and `role: developer`; it uses `store: false`, sends the complete transcript on both stateless requests, streams through `response.completed`, and correlates the tool result with the returned `call_id`. The follow-up replays every item from the completed `response.output` in its original order before appending the matching `function_call_output`, including non-function items such as reasoning. This matches the [official Responses function-calling guide](https://developers.openai.com/api/docs/guides/function-calling). The configured endpoint uses its mocked Chat Completions function tool loop. Neither provider path has a record-write tool. `/practice/agent-draft` is the sole preview path; `/practice/agent-create` recomputes the evidence, values, and digest before atomic create. The UI binds a fresh approval UUID to each explicit click, reuses it only across request retries, and forwards the exact displayed preview for server recomputation. Reusing one UUID with the same body is idempotent; changing its preview or duplicate choice is rejected; a separate explicit duplicate approval uses a new UUID.

The deterministic benchmark covers host verification and create only, not a provider round trip. Its provider entry points are fail-fast patched. Synthetic fixtures check independent values, quote offsets, digest, independently recomputed approval-key fingerprints, stored ID structure/uniqueness, per-create bounded UTC timestamps, full persisted rows, rejection/no-write paths, retry idempotency without changing the original timestamp, and a multi-message Turkish Unicode example. Provider calls, model output quality, and inference latency are excluded.

## Verification

- Desktop: `npm --prefix desktop test` — 40/40 passed, including mocked Responses streams and the full prior-output replay order; no live account call.
- Frontend: `npm --prefix frontend test` — 32/32 passed.
- Frontend production build: `npm --prefix frontend run build` — passed; Vite reports the existing ~824 KB JavaScript chunk warning.
- Focused backend tests: `PYTHONPATH=backend .venv/bin/python -m unittest backend.tests.test_study_agent_practice backend.tests.test_ai_service_practice_tool` — 20/20 passed.
- Full backend tests: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests` — 170/170 passed.
- Host verification/create benchmark: `PYTHONPATH=backend:backend/benchmarks .venv/bin/python backend/benchmarks/benchmark_study_agent_practice.py --repeats 3` — passed for 24 and 100 record workloads; AI excluded, provider entry points trapped, host protocol checked 4 rows, rejected/unapproved/replayed/changed-key paths wrote zero records, and the second explicit identical `new` approval created its own record.
- Bilingual docs generator: `python scripts/build_docs.py` — passed.
- Docs integrity benchmark: `.venv/bin/python scripts/benchmark_docs.py` — passed, 17 rendered pages per locale, 108 evidence excerpts, no errors, AI/network excluded.
- Browser smoke: `HAMARTIA_PYTHON=<worktree>/.venv/bin/python npm --prefix frontend run test:browser` — blocked because the available Playwright Chromium binary cannot load `libglib-2.0.so.0`; this worktree has no system/Nix Chromium executable.
- `git diff --check` — passed.

## Verification limit

No real ChatGPT or local-model request was made. SIWC account eligibility, granted scope, and live acceptance of the additional-tools input item still require the manual consumer-device check. The UI/API local-process boundary assumes the same OS user; it does not defend against another process running as that user and calling the local API directly.
