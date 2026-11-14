# 2026-11-14 topic study chart and full history — plan

## Findings

Project notes include a requirement to track progress with charts. `practice_topic_summaries()` already produces chronological `{date, net, accuracy}` points for each topic, but the UI shows only the text net for the last six sets; the accuracy trend is missing. The UI also has no edit/delete actions for sets older than the last six. This can be addressed using the existing Recharts package without adding a data/API layer.

## Scope

- Show two small, separate line charts for net and accuracy, ordered by set, on each subject/topic card.
- Plot accuracy on a percentage scale using only answered questions in the denominator; blank answers produce no accuracy point.
- Supply all saved sets to the chart; keep the latest six directly manageable in the set list, and allow older sets to be edited/deleted in expandable full history.
- Keep multiple records on the same day as separate points in chronological order.
- Do not change the existing API/model/storage; no real AI call.

## Acceptance and checks

- In a fixture with two sets, show complete, date-ordered net and accuracy values without AI.
- Render single-set / all-blank-answer trends without errors or NaN.
- Allow editing and deleting a record older than six from the expanded list; keep latest-six actions working.
- No overflow at 390 px; charts have accessible names.
- Update frontend test/build, backend regression, and browser smoke/performance measurements.
