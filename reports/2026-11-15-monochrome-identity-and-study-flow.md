# Monochrome identity and study-flow refresh

## Design basis

This pass treats Hamartia as a local-first study tool for recording mistakes, noticing recurring patterns, and choosing a next practice step. It keeps the existing exam, review, plan, progression, Cosmos, ChatGPT, and configured-endpoint flows. The Study Plan's ranked topics are now described as suggestions; students can select any available topic or question. Focused sessions retain their existing pause and cancel controls. A self-check now reports that the user's correct/incorrect choice was saved and that the review queue changed; it does not present that self-report as independently verified learning evidence.

The evidence informs interface choices without claiming that this specific app has been shown to improve outcomes:

- Ryan and Deci's self-determination theory describes autonomy and competence as basic psychological needs relevant to motivation. That supports keeping plan choices optional and making the effect of a self-check visible, while avoiding claims that a particular color or reward mechanism causes motivation. [Ryan & Deci, 2000, DOI 10.1037/0003-066X.55.1.68](https://pubmed.ncbi.nlm.nih.gov/11392867/).
- Hattie and Timperley's feedback model asks where the learner is going, how they are doing, and what to do next; the review also cautions that feedback can have positive or negative effects depending on its form. The Study Plan message therefore confirms the saved action and queue update, without claiming mastery. [Hattie & Timperley, 2007, DOI 10.3102/003465430298487](https://journals.sagepub.com/doi/10.3102/003465430298487).
- Butler found repeated testing produced superior retention and transfer to repeated study in the experiments described in the paper. Hamartia already supports repeat attempts and scheduled review; this visual pass preserves that retrieval practice and does not change the interval algorithm. [Butler, 2010, DOI 10.1037/a0019902](https://pubmed.ncbi.nlm.nih.gov/20804289/).
- WCAG 2.2 Success Criterion 1.4.3 specifies a 4.5:1 minimum for normal text and 3:1 for large text. The refreshed token pairs exceed the normal-text threshold in the measured examples below. [W3C WCAG 2.2 contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

## Identity and interface changes

Two custom path marks were explored. The selected mark has a broken upper route and a lower return stroke: the break suggests a mistake, and the return path suggests reviewing and correcting the route. The second concept was an S-shaped return arrow; it read more like a generic refresh icon, so it was not chosen. The selected geometry is not a typographic H and contains no brain, sparkle, or AI symbol.

The same path geometry now appears in black for light backgrounds, white for the dark app header, and white over a near-black tile for favicons and installer icons. README, desktop application header, both Pages language headers/footers, app favicon, Windows ICO, and Linux 512 px PNG now use the identity. PNG/ICO/SVG previews were inspected at 16, 32, and 512 px. At 16 px the mark is necessarily compact, but its interrupted upper stroke and return route remain visible.

The app keeps its dark layout and moves its former crimson, cyan, indigo, green, and amber accents to neutral gray values. Charts no longer encode positive and negative net with green/red. Study values and actions remain text-labeled, and alerts keep semantic roles. The keyboard focus ring is a 2 px light outline. XP, level, streak, saved progress, and related features/data are retained; the navigation bar no longer uses a colored gradient. Public page structure is unchanged in this PR; only its brand and accent colors are aligned with the monochrome identity.

Measured sRGB contrast ratios using the WCAG relative-luminance formula:

| Foreground / background | Ratio |
| --- | ---: |
| App primary text `#f4f4f5` / base `#09090b` | 18.10:1 |
| App muted text `#a1a1aa` / base `#09090b` | 7.76:1 |
| App primary text `#f4f4f5` / panel `#18181b` | 16.12:1 |
| App button text `#09090b` / accent `#e4e4e7` | 15.68:1 |
| Docs primary text `#181818` / paper `#f5f5f2` | 16.26:1 |
| Docs muted text `#5f5f5f` / paper `#f5f5f2` | 5.85:1 |
| Docs accent `#4c4c4c` / paper `#f5f5f2` | 7.86:1 |

These are token-pair checks, not a claim of full WCAG conformance. Keyboard behavior, mobile layout, and language navigation are checked in the browser smoke; a broader assistive-technology review remains useful.

## Deferred work

The public documentation layout redesign and the Clock tab are intentionally outside this identity pass. The next work is listed in `backlog.md` in this order: an optional Clock tab, repository wiki documentation, stronger system-level non-AI benchmarks, and a docs benchmark last. The current feature keeps its existing session/pause/cancel behavior; no new plan-order preference or engagement mechanic is introduced.

## Verification

- `npm test` in `frontend/`: 18 passed; non-AI utility, format, i18n, and exam-section tests.
- `npm run build` in `frontend/`: passed. Vite continues to report the existing >500 kB JavaScript chunk warning.
- `npm run test:docs` with Nix Chromium: passed for EN default, TR navigation, canonical URLs, narrow layout, brand mark/favicon loading, and no external requests.
- `npm run test:browser` with Nix Chromium and the existing temporary backend workflow: passed with `ai_included: false`; the smoke explicitly asserts there is no `/study-agent/local` request. It also checks loaded app mark/favicon, keyboard focus outline, persistence flows, and the existing EN/TR app interactions.
- Static checks: `git diff --check`, synchronized SVG copy comparison, and visual rendering of brand assets at 16/32/512 px.
- No model, AI endpoint, local provider, or AI benchmark was run.
