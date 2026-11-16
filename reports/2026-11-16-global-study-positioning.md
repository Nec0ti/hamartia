# Global study-tool positioning

Date: 2026-11-16
Scope: Clarify that Hamartia is intended to help learners recognize study errors and patterns across curricula while describing its current exam-format support accurately. This is documentation-only; application behavior and supported formats did not change.

## Changes

- Reframed the internal project purpose, workflow skill description, and README around a study tool for learners across curricula rather than a YKS-only product.
- Clarified that TYT/AYT are the current built-in full-mock formats, while single-subject exams and topic practice are generic; labels and curriculum references are free-form.
- Described selected/custom versioned exact-rational scoring profiles and the legacy YKS rule without presenting either as an official or universal standard.
- Updated the English and Turkish purpose/scope page source and generated pages. User-entered curriculum references remain unverified; no official curriculum or exam alignment is claimed.

## Verification

- `python3 scripts/build_docs.py` — passed; regenerated the bilingual documentation pages from source. The generator also rewrote two unrelated backup pages because their tracked outputs differed from the current generator source; those unrelated generated changes were discarded.
- `python3 scripts/benchmark_docs.py` — passed: 17 routes per locale, 818 local links/assets, 156 exact evidence excerpts, zero errors, `network_access: false`, `ai_included: false`.
- `git diff --check` — passed.

No application build, browser/manual usability run, AI/provider call, or networked service check was run. Human retrieval/usability and fixed-viewport screenshot checks remain open in the backlog.
