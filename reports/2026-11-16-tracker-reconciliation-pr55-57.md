# 2026-11-16 tracker reconciliation: PRs 55–57

## Scope

Updated the English backlog, history, and report index from verified `origin/master` `7ea6f37d55c91f035776a5d770751439be539da3`. PRs #55, #56, and #57 are merged. Releases ARETE-051, ARETE-052, and ARETE-053 are published at the corresponding merge commits:

- PR #55 / ARETE-051: `e58c1ab6a0ed98fa8a4a9c225024662c9c77f3f1`
- PR #56 / ARETE-052: `9a4accc27cc0302d9de6a1a9f25913987da9e388`
- PR #57 / ARETE-053: `0742b61d8fcd2eaa209f0cfff0b5829009f2630b`

These tag targets were checked against `git ls-remote origin`; GitHub reports all three releases published, with ARETE-053 latest.

## Recorded changes and verification

- PR #55 reconciled the backlog/history through #54 and indexed the backup restore report. Its docs integrity command passed for 17 routes per locale. The rendered browser smoke was recorded as passing on 34 pages: reciprocal locale links, section parity, internal links, 390 px layout, and keyboard skip navigation.
- PR #56 changed documentation only. Butler (2010) supports retrieval practice in its studied conditions but does not validate Hamartia's review schedule or establish this app's learning outcomes. WCAG 2.2 SC 1.4.1 was cited for text-labeled controls and charts that do not rely on color alone. No UI or AI behavior changed.
- PR #57 exposed child stdout/stderr on restore CLI failures and fixed the actual failure: the restore had succeeded, then the Turkish success message raised `UnicodeEncodeError` for dotless `ı` under redirected cp1252 stdout. The CLI now writes UTF-8, with a regression assertion. The full Windows backup module passed 28 tests with the POSIX-only mode test skipped; Linux passed 27 tests with the Windows-only test skipped, including forced cp1252 output encoding.
- The original broader Windows failure is now diagnosed as this post-restore output-encoding bug. Windows process-termination recovery and `MOVEFILE_WRITE_THROUGH` do not prove power-cut durability; physical Windows storage/filesystem validation remains open.

No local AI, real provider, or external model execution was used. Keep physical-device checks, the human docs cohort, account/profile deletion and retention pending user choice, real SIWC/provider checks, and legal/hosting gates open.

## Current checks

- `python3 scripts/benchmark_docs.py --output /tmp/hamartia-pr58-docs-integrity.json` — passed on this worktree; 17 routes per locale, no integrity errors, `ai_included: false`, and no network access.
- `git diff --check` — passed.
- Attempted the rendered docs browser smoke with the PR #55 command; it could not start because this fresh worktree has no installed frontend `playwright` module. The previously recorded PR #55 browser smoke result is retained with that provenance; no dependency installation was performed.
