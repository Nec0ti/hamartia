# Study Agent CLI Core

## Scope

Added a JSON-lines command entry point:

```sh
PYTHONPATH=backend python -m app.hamartia_cli --jsonl
```

Each input line is a strict JSON object with the only supported command `study.practice.prepare`. The request contains the selected `en`/`tr` language, the student's bounded messages, and provider-suggested `{field, quote}` hints. The standalone JSON-lines process accepts transcript input from a trusted local caller; it is not exposed as a shell command to the model. The model-callable schema is narrower: it accepts only evidence quotes. The provider host injects the actual UI transcript and selected language through `dispatch_provider_tool`, rejecting any tool arguments that add transcript, language, index, value, path, or extra command fields. The tool emits a deterministic progress/preview response and has no create, update, delete, settings, backup, provider, or shell capability. Duplicate JSON keys and oversized lines are rejected by a bounded reader.

The parser accepts only a narrow tested subset of English and Turkish statements. It verifies the exact quote occurs once in the actual student transcript, derives the value locally using field-specific grammar, examines the full sentence for negation, hedging, hypotheticals, questions, and reported speech, and scans for competing same-field values so a provider cannot cherry-pick one side of a sentence. It records the source message index and character offsets itself. A transcript-wide resolver checks candidate values in source order even when the provider omits later evidence; conflicting or hedged continuations remain ambiguous, while a later explicit correction is accepted only when its exact source clause is found and parsed locally. Relative-day continuations across messages remain ambiguous. Numeric boundaries reject negative, decimal, and thousands-separated partial matches in both natural and labeled forms, including space-separated thousands. Count ranges and alternatives (including digit/word-number `or`/`veya`, comma-plus-connector, and labeled counts), mixed ISO/slash/dotted/named dates including shorthand continuations (`November 15 or 16`, `2026-11-15 or 11/16`), YMD slash/dot and DMY hyphen forms with ordinal suffixes, and duration alternatives across digit/word-number units remain ambiguous even when a quote selects one value. Any hour expression keeps minute/second extraction unresolved, and additive same-unit phrases (such as `45 minutes plus thirty minutes`) are not combined. Slash, decimal, and Unicode fractions remain unresolved. Unknown or unsupported phrasing produces a natural-language clarification question in the selected language; it is not guessed. Relative dates, non-ISO ambiguous dates, approximate or clock-style durations, net scores used as correct counts, and aggregate `x of y` counts remain unresolved.

This is the CLI core contract only. ChatGPT Responses and configured Chat Completions tool loops are not integrated yet, so this checkpoint is not the completed user-facing conversational agent. Record creation remains exclusively in the existing app exact-preview approval flow.

## Verification

No provider or local model calls were made.

- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest backend.tests.test_study_agent_cli backend.tests.test_study_agent_practice -v` — 31/31 passed, including host transcript/language binding, forged/duplicate/Unicode evidence, count/date/duration alternatives, shared labeled and natural numeric boundaries, and oversized-input draining.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest discover -s backend/tests -v` — 162/162 passed.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m app.hamartia_cli --jsonl` — manual JSON-lines invocation returned bounded clarification and rejected an unsupported delete command.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python backend/benchmarks/benchmark_study_agent_cli.py --repeats 3 --json-output /tmp/hamartia-study-agent-cli-benchmark.json` — passed with EN natural/labeled and TR natural/labeled fixtures, independent value/evidence/digest oracles, exact `ambiguous` versus `incomplete` checks, and 57 adversarial probes per run. Transcript-boundary probes check that omitted later conflicts and hedge continuations remain ambiguous, exact correction evidence replaces stale evidence, and relative-day continuations remain ambiguous. Every CLI result explicitly has `write_allowed:false`; a benchmark self-check rejects absent, null, true, or numeric false-like values. `ai_included:false`; source inspection confirms provider and persistence services are structurally excluded from the CLI path. Side effects are not runtime-instrumented or reported as observed zero counts. Latest p50 was 0.156174s for 24 entries and 0.699342s for 100 entries.

The benchmark is wired into backend CI. Provider transport loops, live SIWC function-call capability, endpoint compatibility, and browser interaction remain to be implemented/verified; no live-account or remote endpoint test was attempted.
