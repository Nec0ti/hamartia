# Documentation retrieval benchmark hardening

## Change

The v2 pack preserves the original ten paired EN/TR tasks and adds three more difficult multi-page synthesis pairs. They require readers to distinguish user-defined scoring labels from official alignment, immutable record snapshots from later profile edits, the Study Agent's separate data paths and consent gates, and backup contents/key handling/restore failure semantics. Each added task has five manually mapped rubric criteria with evidence quotes and page/section anchors in both locales. The profile and provider-path pairs are critical.

The public task pack remains fixed and inspectable. Withholding the answer key during a session can reduce direct exposure, but cannot prevent prior inspection, memorization, or evaluator bias. The prompts and key therefore do not establish an adversarially sealed test.

## Integrity check

Command: `python3 scripts/benchmark_docs.py`

The offline checker passed with no errors. It checked 26 paired locale prompts/rubrics, 142 exact evidence excerpts (140 from rendered pages and two from the protocol), 818 local links/assets, three synthetic decoys, and the input-hash sensitivity checks. The task set is 13 pairs / 65 points per locale / 130 total. Gates are 56/65 per tester, 117/130 combined cohort means, and full credit for each of six critical paired tasks.

The generated result is [`2026-11-16-docs-benchmark-hardening-results.json`](2026-11-16-docs-benchmark-hardening-results.json). It records `ai_included: false` and `network_access: false`. No local AI, model endpoint, provider, or external link was called.

## Human validation status

**NOT RUN.** No tester answered or scored these prompts; no screenshot/usability evaluation was performed. The automated checker confirms structural integrity and quoted excerpt presence. It does not prove that evidence semantically entails each criterion, task difficulty, translation quality, rubric completeness, or a reader's retrieval ability. Human validation remains open in the backlog.
