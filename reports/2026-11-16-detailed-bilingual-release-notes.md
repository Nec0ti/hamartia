# Detailed bilingual release notes

Date: 2026-11-16
Scope: Require each merged pull request to provide truthful, detailed English and Turkish user-facing release notes, then generate the automatic ARETE note from that merged pull request. Existing release entries remain unchanged.

## Changes

- Added a root repository rule requiring an English internal workflow and a filled bilingual release summary on every PR merged to `master`.
- Added a PR template with structured English and Turkish fields for highlights, behavior and reason, how to use, compatibility/migration, verification, and not-run checks/known limitations.
- The release generator parses only the marked summary from the merged PR body, requires every field in both languages, and publishes those details with the PR link. Missing or blank fields fail the release instead of being replaced by generic or inferred claims.
- PR titles and summary text are rendered safely: only the PR number is a link; title and field content have HTML and Markdown syntax escaped. Plain paragraphs and simple ordered/unordered lists stay readable; embedded headings, links, tables, code syntax, and raw HTML display as text.
- The template and repository rule require documentation-only/internal-only PRs to state that user behavior did not change and explain the internal change. The automatic release-after-merge workflow and existing releases were not changed.

## Verification

- `python .github/scripts/test_release_metadata.py`: passed (6 tests). Tests cover bilingual field rendering, empty/missing summary rejection, hostile title and Markdown content, ARETE numbering, merged-PR selection, idempotent release ledger append, artifact checks, and first publication.
- `git diff --check`: passed.
- No package builds, local AI, provider calls, or server were run. The normal CI/release workflow will still build packages after merge.
