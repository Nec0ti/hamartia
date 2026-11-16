# Study Agent CLI record workflows

## Scope

The JSON-lines host interface now supports all five existing Study Agent write paths:

| Draft | Separate approval | Persisted record |
| --- | --- | --- |
| `study.practice.draft` | `study.practice.approve` | PracticeSession |
| `study.learning_evidence.draft` | `study.learning_evidence.approve` | LearningEvidence |
| `study.question.draft` | `study.question.approve` | Text-only Question |
| `study.exam.draft` | `study.exam.approve` | Single-subject branch Exam |
| `study.sectioned_exam.draft` | `study.sectioned_exam.approve` | Sectioned TYT/AYT Exam |

The existing `study.practice.prepare` command remains read-only and backward compatible. New commands call the corresponding API request models and host draft/create handlers directly; they do not create a second parser, persistence path, or record format. Commands use the selected `en` or `tr` language, and the existing signed continuation tokens bind language and transcript for multi-turn evidence flows.

Run the source checkout with `PYTHONPATH=backend python -m app.hamartia_cli --jsonl`; each bounded input line is one JSON command and each output line is one JSON result. The default data directory follows the existing `HAMARTIA_DATA_DIR` configuration. The desktop package does not currently expose this Python entrypoint as a separate terminal command.

Draft commands accept the student transcript and evidence-only `{field, quote}` hints. Existing host verifiers locate each exact quote, derive values, reject unsupported or conflicting evidence, and return missing/ambiguous questions plus the canonical preview and digest. Draft results always have `write_allowed: false` and do not persist anything. Extra fields and caller-supplied values are rejected. The CLI does not invoke a model or provider.

Approval is a different command. It requires `approved: true`, the original transcript, full canonical fields/evidence, exact digest, and a stable approval UUID. The CLI rejects a caller-supplied parsed `proposal`; PracticeSession's legacy create handler requires that field, so the CLI recomputes it from the transcript and verified quotes on the host before calling that handler. All five existing create handlers recompute and validate the preview before their atomic, idempotent write. Saved responses include the persisted record and confirmation status.

Example practice draft:

```json
{"command":"study.practice.draft","language":"en","messages":["...student statement..."],"evidence_claims":[{"field":"date","quote":"on 2026-11-16"}]}
```

Review the returned questions and complete preview in the caller. After explicit user approval, send the same conversation and preview fields to `study.practice.approve` with the returned `preview_digest`, a new UUID `approval_id`, and `approved: true`. Reuse that UUID only for an exact retry; changed approvals are rejected by the existing create handler.

## Verification

- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest backend.tests.test_study_agent_cli -v` — 22/22 passed. Coverage includes complete create/retry flows for all five record types; zero writes after drafts and incomplete/ambiguous inputs; English and Turkish questions; rejection of caller proposals and unknown/provider-value fields; and zero provider calls in the full-flow test using fail-fast `AIService` method tripwires.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python -m unittest discover -s backend/tests -v` — 317 tests passed; 12 PostgreSQL integration tests were skipped because no test database was configured.
- `PYTHONPATH=backend /tmp/hamartia-cli-venv/bin/python backend/benchmarks/benchmark_study_agent_cli_records.py --repeats 3` — passed three warm repetitions of all five draft, no-write, approval, and exact-retry flows. The benchmark reports `ai_included: false`, `provider_calls: 0` with fail-fast tripwires, and `external_connect_attempts: 0` with socket tripwires. On the recorded Linux/Python 3.14.8 host, warm p50 was 261.3 ms and p95 was 262.6 ms for five persisted records including approval retries.
- Existing CLI parser suite remained green. No local model/provider, live endpoint, browser, physical device, or social service was exercised.

## Limits

This is a local host command contract. A caller must present the localized questions and exact preview, collect the user's approval, and then send the separate approval command. The CLI does not itself provide a terminal confirmation UI or ChatGPT/OpenAI-compatible provider transport. Existing desktop ChatGPT-plan default and explicitly selected configured-endpoint integrations are unchanged. As with the other local APIs, the approval flow is not a security boundary against another process running as the same OS user.
