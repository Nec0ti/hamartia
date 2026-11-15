# Human task administration

The task workbook is `tasks.json`; the separate scoring key is `answer_key.json`. The repository is public and both files can be inspected, so the pack is reproducible but not a sealed blind test. For a blinded administration, give the participant only a generated booklet and the wiki, and do not give them this repository or the answer key. This reduces direct key exposure during a session but cannot prevent prior inspection or memorization.

Use at least **two independent testers** for each language. Each tester must complete both locale booklets in separate sessions so that overall and per-locale gates can be scored for each person. Do not let testers discuss task answers or see the answer key before submission. Each tester should receive only the generated booklet and the wiki, and should not have access to the repository during the run. The files remain public and inspectable, so this procedure cannot prevent prior inspection or memorization.

Generate stable, independently shuffled booklets for both locales:

```sh
python3 scripts/benchmark_docs.py --booklet-locale en --seed 20261115
python3 scripts/benchmark_docs.py --booklet-locale tr --seed 20261115
```

The output contains prompts and order only; it omits task IDs, critical flags, and scoring key. Changing the seed produces a different deterministic order. Use a fresh browser profile for each tester and record each booklet seed. Ask for a short answer and the cited wiki page/section anchor for every task. Do not use an AI tool, model endpoint, external search result, or another person's answer. The synthetic `example.invalid` link and absent local decoys are not to be opened or fetched.

Run the screenshot task at **390×844 CSS pixels** and capture the final page after the language switch, with its heading and documentation navigation visible. Screenshots are reviewed by a human; do not attach or retain images containing real study records, credentials, or personal data. For accessibility observations, record the keyboard action and the documented limitation separately from a screen-reader certification claim.

Score each criterion as one point only when the answer includes the supported fact and cites relevant evidence. A statement contradicting a critical boundary receives no credit for that criterion. Apply thresholds from `answer_key.json` independently to each tester's complete 100-point run: at least 90/100 overall, at least 43/50 in each locale, and full credit on all four critical task pairs in both languages (eight localized task entries). Do not average away a failed critical task or a failing tester. Record the task-set SHA-256, rendered-wiki SHA-256, locale booklet seeds, per-locale scores, critical-task scores, citations, and elapsed time for each tester. The default integrity JSON contains the two hashes for the exact files under evaluation. A task's completion time may be recorded as descriptive data but is not a pass gate.
