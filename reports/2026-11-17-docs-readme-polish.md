# Documentation and README presentation polish

## Scope

Kept the static GitHub Pages generator and 17 EN/TR page IDs. Added grouped, expandable navigation with one open group for the active page; product links, desktop package semver sourced from `desktop/package.json`, breadcrumbs, a section-linked page contents panel, and a feedback link. Styled the wiki for wide, tablet, and mobile viewports. The Getting Started page now includes a bilingual topic/description guide table. Study workflows gained two-level headings for scoring snapshots and practice trends. The FAQ adds source-backed answers about the local student profile and immutable scoring-profile snapshots. Backup pages now say that optional onboarding/profile data is included. The README now gives direct guide/release links, a feature map, a short source quickstart, local-data/provider disclosures, platform packages, project status, and license.

The remaining page bodies were inspected and retained because they already provide useful detail and supported procedures: Study Agent, privacy and consent, backup and restore, exam formats and Maarif, learning evidence, Clock, installation, troubleshooting, accessibility, purpose/scope, Cosmos, mistakes/review, system architecture, and contributing. No screenshots were added to the repository.

## Verification

- `python3 -m py_compile scripts/build_docs.py` — passed.
- `python3 scripts/build_docs.py` — generated 34 static pages.
- `python3 scripts/benchmark_docs.py --output /tmp/hamartia-docs-readme-integrity-final.json` — passed offline: 17 routes per locale, 34 active navigation items, 17 paired H2 anchor orders, 1,060 local links/assets, 156 exact evidence excerpts, 26 rubric entries, and zero errors. `ai_included` is false and `network_access` is false. Rendered-wiki SHA-256: `b40ff01d44d78e7a607e823b4405869b711d3b3a855b56f85ee550e3a19973fb`.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) NODE_PATH=/home/necoti/hamartia-clock/frontend/node_modules npm --prefix frontend run test:docs'` — passed for all 34 routes, reciprocal locale links, grouped active navigation, TOC/section correspondence, internal links, 390 px overflow, and keyboard skip navigation.
- Captured and visually inspected Getting Started and Study Agent at 1440 px and 390 px. Temporary captures: `/tmp/hamartia-docs-home-desktop.png`, `/tmp/hamartia-docs-home-mobile.png`, `/tmp/hamartia-docs-study-agent-desktop.png`, and `/tmp/hamartia-docs-study-agent-mobile.png`.
- `git diff --check` — passed.

## Limits

This was a documentation and README change; application suites and model/provider flows were not run. External source and download links were syntactically counted but not fetched. The screenshot captures were internal visual review, not the pending human retrieval/usability cohort or a full accessibility audit. No model or AI call was made.
