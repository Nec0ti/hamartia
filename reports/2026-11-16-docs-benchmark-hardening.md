# Documentation retrieval benchmark hardening

## Change

The v2 pack preserves the original ten EN/TR task pairs and adds three paired challenges for profile authority/versioning, provider data flows/consent, and backup credentials/restore failures. The workflow and learning-evidence tasks now require evidence from two independent wiki pages; the restore task is correctly labeled as a one-page boundary retrieval task. In total, six task pairs marked `multi_page_synthesis` cite at least two wiki pages in both locales, and the integrity checker enforces that minimum.

The old synthetic missing-route, missing-anchor and `example.invalid` stimuli are removed from participant prompts. The related link targets remain only as checker fixtures in `docs/benchmark/integrity_fixtures.json`; they are not shown to testers or presented as wiki evidence. The stale-reference task instead tests claims against actual exam/Maarif page content and its linked 2026 references. Its rubric has five distinct criteria without duplicate claims.

The public task workbook and key remain fixed and inspectable. Withholding the key during a session can reduce direct exposure, but cannot prevent prior inspection, memorization or evaluator bias. This is not a sealed blind test.

## Integrity check

Command: `python3 scripts/benchmark_docs.py`

The offline checker passed with no errors. It checked 26 paired locale prompts/rubrics, 156 exact evidence excerpts (154 rendered-page and two protocol), 818 local links/assets, three checker-only integrity fixtures, six correctly cross-page synthesis pairs in both locales, and input-hash sensitivity. The task set is 13 pairs / 65 points per locale / 130 total. The proposed gates are 56/65 per tester, 117/130 combined EN/TR cohort means, and full credit on each of six critical task pairs. They are provisional hypotheses, not validated thresholds; human pilot results must be used to review them.

The generated result is [`2026-11-16-docs-benchmark-hardening-results.json`](2026-11-16-docs-benchmark-hardening-results.json). It records `ai_included: false`, `network_access: false`, and `human_thresholds: provisional_pending_human_pilot`. No local AI, model endpoint, provider or external link was called.

## Human validation status

**NOT RUN.** No tester answered or scored these prompts; no screenshot/usability evaluation was performed. The automated checker confirms structural integrity, the number of cited pages for tasks labeled multi-page, and quoted excerpt presence. It does not prove semantic entailment, task difficulty, translation quality, rubric completeness or retrieval ability. Human validation remains open in the backlog.
