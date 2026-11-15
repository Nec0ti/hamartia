# Bilingual documentation retrieval benchmark

## Scope

This PR adds a versioned, independently authored task pack for the shipped 17-page English and Turkish wiki. It contains ten paired natural-language tasks total (20 locale-specific prompts, ten per locale) and a separate five-point-per-task answer key with manually written criteria and exact page/anchor excerpts. The task set covers cross-page workflow synthesis, false and unsupported premises, privacy/provider boundaries, Clock delivery limits, backup replacement/snapshot semantics, review intervals, misleading/stale decoys, learning-claim limits, and fixed-viewport language-switch screenshots.

Four paired tasks are critical gates: exam/Maarif scope, progress/mastery claims, privacy/provider boundaries, and Clock delivery limits. The human scoring thresholds are **at least 90/100 overall**, **at least 85% in each locale** (at least 43/50 with whole-point scoring), and **full credit on every critical task in both locales**. The administration protocol uses separate cohorts to prevent cross-language answer priming: at least two independent testers per locale, each sees only one language, and each receives a distinct seeded order. Every tester must score at least 43/50; the mean English cohort score plus the mean Turkish cohort score must total at least 90/100; every tester must earn full credit on all four critical tasks in their locale. Scoring criteria ask for supported answers and page evidence; unsupported claims lose the associated point. Screenshot evidence is scored by a human only.

The task workbook and answer key are checked into this public repository and are inspectable. An evaluator can withhold the key during a human session, but repository access means this is not a cryptographically sealed or adversarially hidden test. Repeated exposure can teach the fixed prompts. The false-premise, cross-page, and decoy tasks make the set harder to pass through one-page lookup, but do not eliminate memorization or evaluator bias.

## Automated integrity run

Command:

```sh
python3 scripts/benchmark_docs.py
```

The Python standard-library checker parses the actual rendered HTML pages in `docs/`. It checks each locale's route count and `lang`, one H1, duplicate IDs, matching navigation order and active page, matching EN/TR H2 anchor order, local routes/assets/fragments, and every answer-key excerpt against the cited section in the cited rendered page. It also checks task pairing, rubric point totals, critical-gate parity, and that the synthetic missing-route/missing-anchor/stale-link fixtures remain synthetic.

The checked-in result is [`2026-11-15-docs-benchmark-results.json`](2026-11-15-docs-benchmark-results.json):

- The static check completed in **0.27 seconds** under Python 3.14.8 on this host. This is checker runtime, not documentation retrieval performance.
- Task-pack SHA-256: `cc552da13e3102ada36a50bfe611b791eb6bd5fb4c86e8e2a23649118bd482a0`; rendered-wiki SHA-256: `ea5376db9f4f74eb18c94ad16c7b555a8be25980e3a075eef01e619ce803f3d0`.
- Protocol SHA-256: `d2170c2ed0ab0a1496e613cf2ac7d10d75160f6ba54b6698f70f391aae4db26c`; checker SHA-256: `75af5c987fba221b609884f81cb9c44c94bc8230c0786141f5017e2d8d4d2645`.
- In-memory sensitivity checks perturbed all three task-pack files, all 37 rendered-wiki files, the protocol, and the checker, and confirmed each corresponding digest changes.
- 17 rendered pages and 17 navigation routes in each locale; 34 active navigation items checked.
- 17 paired H2-anchor orders checked.
- 816 local links/assets checked and 120 external references counted syntactically. External links are **not fetched** and their availability is not asserted.
- 20 localized answer rubrics; 104 exact excerpts checked in rendered page sections and two screenshot-protocol excerpts checked in the human administration README.
- Three synthetic decoys checked: an absent local route, an absent local anchor, and a reserved `example.invalid` stale-link example. No external request is made.
- `ai_included: false`, `network_access: false`; the task answer and screenshot scoring fields remain `pending` / `pending_manual`.

The automated result measures wiki/task-pack integrity only. It parses rendered HTML and confirms exact excerpt presence at cited page sections; it does **not** prove semantic entailment, that a quote supports its rubric criterion, translation quality, task difficulty, rubric completeness, or correctness of a human response. A human assessor must judge whether each answer is accurate, complete, and supported by its cited evidence. It does not score whether a reader can find or synthesize an answer, measure completion time, inspect a screenshot, or assess accessibility with assistive technology. No human task session or screenshot evaluation was conducted for this report. Such results must be recorded separately against the human rubric; they must not be inferred from the automated pass. The administration protocol requires separate cohorts with at least two testers per locale, each seeing only one language, and applies locale/critical gates per tester. See [`docs/benchmark/README.md`](../docs/benchmark/README.md) for booklet generation, fresh-profile use, key withholding, and hash/seed recording.

## Reproducibility and boundaries

The task set uses stable IDs and fixed wording, version `1`, and does not sample tasks; the nine retrieval tasks are shuffled from a recorded seed, with the screenshot task last so its paired-language page cannot prime earlier answers. The checker is deterministic and writes the same static result fields for unchanged files. The answer rubric is separate from the prompts to support evaluator-withheld-key administration, but both files are public. Human results should record task ID, locale, rubric points, cited page/anchor, booklet seed, all four SHA-256 values, and elapsed time without retaining participant names, private study data, credentials, or screenshots containing personal records.

The benchmark does not load or call a model, local AI service, or provider. It has no network dependency and performs no live external-link validation. Browser navigation, screenshot capture at 390×844, visual usability, and human response scoring remain manual work.
