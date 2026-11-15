# Bilingual documentation wiki

## Scope

Replaced the former single-page English/Turkish guide with a generated static wiki. Each locale has the same 16 page IDs in the same navigation order, with Getting Started first. The page catalog lives in `scripts/build_docs.py`; generated HTML is in `docs/` and is published by the existing GitHub Pages workflow.

The pages cover Getting Started, system architecture, purpose/scope, study workflows, mistakes and review, exam formats and Maarif, installation, Study Agent/providers, privacy/consent, backup/restore, Clock/reminders, accessibility/language, learning-evidence limits, FAQ, troubleshooting, and contributing. Cross-links and language-switch links point to the matching page in the other locale.

Content was checked against the merged app behavior and current project notes. Important boundaries documented include: YKS wrong-answer penalty and unsupported exam adaptation; Maarif as curriculum, not an exam type or verified alignment; user-entered references; separate Study Agent and question-analysis payloads; endpoint locality not verified; API-key and ChatGPT-credential backup exclusions; local-clock timezone behavior; and no notification guarantee when Hamartia is closed or the device is asleep. The evidence page links to relevant learning research and avoids grade/mastery claims.

## Verification

- `python3 -m py_compile scripts/build_docs.py` — passed.
- `python3 scripts/build_docs.py` — generated 32 static HTML pages from 16 EN/TR page pairs.
- `git diff --check` — passed.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) NODE_PATH=/home/necoti/hamartia-clock/frontend/node_modules npm --prefix frontend run test:docs'` — passed. The smoke visited all 32 routes and checked the page language, one H1, one active navigation item, 16-item menu with Getting Started first, reciprocal locale route, matching section IDs between translations, local links, 390px overflow, and keyboard skip link. Page loading issued no external requests.

The smoke reused the existing Playwright installation from the Clock worktree and a Nix-provided Chromium binary; it did not change the frontend dependency lock. No AI/model/provider call or benchmark was run. The planned blind bilingual docs retrieval benchmark is intentionally deferred to its later project phase.

## Limits

The browser smoke checks static page structure, links, narrow viewport overflow, and a basic keyboard route. It is not the planned retrieval benchmark, a full WCAG audit, screen-reader certification, manual verification of provider behavior, or packaged Windows/Linux notification testing. The release links and time-sensitive official exam references should be reviewed as those destinations change.
