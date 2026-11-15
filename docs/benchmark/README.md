# Human task administration

The task workbook is `tasks.json`; the separate scoring key is `answer_key.json`. The repository is public and both files can be inspected, so the pack is reproducible but not a sealed blind test. For a blinded administration, give the participant only a generated booklet and the wiki, and do not give them this repository or the answer key. This reduces direct key exposure during a session but cannot prevent prior inspection or memorization.

Use at least **two independent testers per locale**. Each participant sees only one locale; do not ask a tester to complete both language versions, because the paired tasks can reveal answers across languages. Do not let testers discuss answers or see the answer key before submission. Each tester should receive only their generated booklet and the wiki, and should not have repository access during the run. The files remain public and inspectable, so this procedure cannot prevent prior inspection or memorization.

Generate stable, independently shuffled booklets for both locales:

```sh
python3 scripts/benchmark_docs.py --booklet-locale en --seed 20261115
python3 scripts/benchmark_docs.py --booklet-locale tr --seed 20261116
python3 scripts/benchmark_docs.py --booklet-locale en --seed 20261117
python3 scripts/benchmark_docs.py --booklet-locale tr --seed 20261118
```

The first two commands are example booklets for one tester per locale; the next two use different seeds for a second tester per locale. The output contains prompts and order only; it omits task IDs, critical flags, and scoring key. Changing the seed produces a different deterministic order for the retrieval tasks; the screenshot task stays last because it opens the paired-language page. Use a distinct seed for every participant and record it. Use a fresh browser profile for each tester. Ask for a short answer and the cited wiki page/section anchor for every task. Do not use an AI tool, model endpoint, external search result, or another person's answer. The synthetic `example.invalid` link and absent local decoys are not to be opened or fetched.

## Screenshot task

Run the screenshot task at 390×844 CSS pixels and capture the final page after the language switch, with its heading and documentation navigation visible. Screenshots are reviewed visually by a human; OCR or text matching alone cannot award the screenshot point. Do not attach or retain images containing real study records, credentials, or personal data. For accessibility observations, record the keyboard action and the documented limitation separately from a screen-reader certification claim.

Score each criterion as one point only when the answer includes the supported fact and cites relevant evidence. A statement contradicting a critical boundary receives no credit for that criterion. Each tester must score at least 43/50 in their assigned locale. For the overall gate, add the mean EN cohort score (out of 50) to the mean TR cohort score (out of 50); the combined result must be at least 90/100. Every tester must receive full credit on all four critical tasks in their locale, covering all four critical task pairs across both cohorts. Do not average away a failing tester or critical task. Record the task-pack, rendered-wiki, protocol, and checker SHA-256 values, each locale booklet seed, locale score, critical-task scores, citations, and elapsed time for every tester. The default integrity JSON contains the four input digests; the checker verifies that in-memory changes to every hashed task-pack and rendered-wiki member, the protocol, and its own source change the corresponding digest. Completion time is descriptive, not a pass gate.
