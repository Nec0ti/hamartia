# Study Agent CLI Core

## Scope

Added a JSON-lines command entry point:

```sh
PYTHONPATH=backend python -m app.hamartia_cli --jsonl
```

Each input line is a strict JSON object with the only supported command `study.practice.prepare`. The request contains the selected `en`/`tr` language, the student's bounded messages, and provider-suggested `{field, quote}` hints. The standalone JSON-lines process accepts transcript input from a trusted local caller; it is not exposed as a shell command to the model. The model-callable schema is narrower: it accepts only evidence quotes. The provider host injects the actual UI transcript and selected language through `dispatch_provider_tool`, rejecting any tool arguments that add transcript, language, index, value, path, or extra command fields. The tool emits a deterministic progress/preview response and has no create, update, delete, settings, backup, provider, or shell capability. Duplicate JSON keys and oversized lines are rejected by a bounded reader.

The parser accepts only a narrow tested subset of English and Turkish statements. It verifies the exact quote occurs once in the actual student transcript, derives the value locally using field-specific grammar, examines the full sentence for negation, hedging, hypotheticals, questions, and reported speech, and scans for competing same-field values so a provider cannot cherry-pick one side of a sentence. It records the source message index and character offsets itself. Contradictions remain ambiguous until explicit correction. Numeric boundaries reject negative, decimal, and thousands-separated partial matches in both natural and labeled forms, including space-separated thousands. Count ranges and alternatives (including digit/word-number `or`/`veya`, comma-plus-connector, and labeled counts), mixed ISO/slash/dotted/named dates, and duration alternatives across digit/word-number units (including fractional phrases such as `half an hour` and `bir buçuk saat`) remain ambiguous even when a quote selects one value. Unknown or unsupported phrasing produces a natural-language clarification question in the selected language; it is not guessed. Relative dates, non-ISO ambiguous dates, approximate or clock-style durations, net scores used as correct counts, and aggregate `x of y` counts remain unresolved.

This is the CLI core contract only. ChatGPT Responses and configured Chat Completions tool loops are not integrated yet, so this checkpoint is not the completed user-facing conversational agent. Record creation remains exclusively in the existing app exact-preview approval flow.

## Verification

No provider or local model calls were made.

- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest backend.tests.test_study_agent_cli backend.tests.test_study_agent_practice -v` — 31/31 passed, including host transcript/language binding, forged/duplicate/Unicode evidence, count/date/duration alternatives, shared labeled and natural numeric boundaries, and oversized-input draining.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest discover -s backend/tests -v` — 162/162 passed.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m app.hamartia_cli --jsonl` — manual JSON-lines invocation returned bounded clarification and rejected an unsupported delete command.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python backend/benchmarks/benchmark_study_agent_cli.py --repeats 3 --json-output /tmp/hamartia-study-agent-cli-benchmark.json` — passed with diversified EN/TR natural and labeled fixtures, independent value/evidence/digest oracles, exact `ambiguous` versus `incomplete` checks, correction/conflict/duplicate/cherry-pick controls, `ai_included:false`, zero provider calls, zero writes, and 20 adversarial probes per run. Latest p50 was 0.081400s for 24 entries and 0.354528s for 100 entries.

The benchmark is wired into backend CI. Provider transport loops, live SIWC function-call capability, endpoint compatibility, and browser interaction remain to be implemented/verified; no live-account or remote endpoint test was attempted.
