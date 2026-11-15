# Conversational Study Agent Practice Entry

## Scope

This first vertical slice adds an explicitly invoked Study Agent flow that creates `PracticeSession` records only. ChatGPT remains the default provider and the existing configured OpenAI-compatible endpoint remains optional. Provider output is an untrusted closed-schema proposal; all accepted values and field-level provenance are recomputed from the student's current messages by deterministic server code. The app does not send saved records or the general study summary in this workflow.

The student can correct an entry conversationally. Missing, ambiguous, malformed, or invalid required values produce deterministic questions in the saved `en` or `tr` language. Provider guesses are discarded and surfaced as a mismatch notice followed by the same question. The UI privately accumulates provider streaming output and does not display raw JSON before server validation. A complete preview shows the values and student-message quotes. Approval is bound to the exact normalized proposal, evidence, and preview digest; stale or altered previews fail. Duplicate detection occurs inside the atomic storage update, with explicit new-record or cancel choices. No updates/deletes, arbitrary tools, backups, settings, or unallowlisted record types are exposed.

The local API is available to the same user process and does not authenticate local callers. The exact preview confirmation is enforced in the app UI and validated by the API; this boundary is not intended to protect against another process running as the same user and directly calling the local API.

## Verification

All provider transports were mocked for tests and browser smoke. No ChatGPT or local-AI call was made; model quality is excluded from tests and benchmarks.

- Focused backend: `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest discover -s backend/tests -p 'test_study_agent_practice.py' -v` — 13/13 passed. Includes configured-provider overguess recovery, localized missing-field prompt, zero writes, strict schema, invalid values, conflict/correction, exact approval, concurrent duplicate approvals, and mocked transport.
- Full backend: `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest discover -s backend/tests -v` — 144/144 passed.
- Frontend: `npm test` — 32/32 passed.
- Desktop: `npm test` — 38/38 passed, including ChatGPT IPC workflow/language forwarding and no real provider access.
- Production frontend: `npm run build` — passed. Vite reports the existing large-chunk warning (~823 KB minified JavaScript).
- Browser: `HAMARTIA_PYTHON=/tmp/hamartia-cli-venv/bin/python PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:browser` — passed; mocked provider, raw JSON invisibility assertion, deterministic clarification, no premature write, exact preview, and save all ran with `ai_included:false`.
- Public docs: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:docs` — passed for 34 pages, reciprocal locale links, section parity, internal links, 390px layout, and keyboard skip link. The host Playwright-bundled Chromium could not load `libglib-2.0.so.0`; the Nix Chromium executable passed.
- Docs generation: `python scripts/build_docs.py` — passed; generated English and Turkish wiki pages include the entry workflow and provider payload details.
- AI-free benchmark: `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python backend/benchmarks/benchmark_study_agent_practice.py --repeats 3 --json-output /tmp/hamartia-study-agent-practice-benchmark.json` — passed. It uses a seed-fixed synthetic fixture and an independent expected-row oracle built from the input fixture plus returned IDs/timestamps; persisted full rows include values, derived net/accuracy, and metadata. For 24 and 100 rows, provider calls were 0, mismatch writes were 0, and unapproved duplicate writes were 0. Results: 24 rows p50 0.184269s; 100 rows p50 0.929509s. Benchmark wired into backend CI.
- `git diff --check` — pending final checkpoint.

## Remaining work

This is only the `PracticeSession` slice; the broader CLI backlog remains open for additional allowlisted record types. Real ChatGPT/configured-provider execution is intentionally untested and must be checked on the separate computer. The local same-user process trust boundary and consumer-machine behavior should remain explicit.
