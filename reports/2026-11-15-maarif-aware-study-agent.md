# Maarif-aware Study Agent and user-entered curriculum references

## Scope

Each missed-question record can carry an optional user-entered curriculum reference: framework, source name, version/year, grade/year, unit/theme, short outcome note or paraphrase, process component, and optional source URL. The existing subject field supplies course/subject. Text is capped, and source URLs must be absolute HTTP(S) URLs without userinfo, query, or fragment. Hamartia never fetches or verifies a source URL; users may open it themselves. Existing records and backups load with an empty reference. API updates preserve the reference when omitted or null and clear it with an empty object.

The Questions view supports create/edit/search and marks references as user-provided and unverified. The Study Agent context for both ChatGPT and the configured OpenAI-compatible endpoint includes at most eight distinct references from active missed questions, within the same 6,000-character bounded summary. It excludes saved question text and images. Per-request consent names the categories and recipient; the configured endpoint consent names its exact URL, possible remote operation, saved API-key transmission for authentication, and endpoint-side retention. ChatGPT remains the default. Providers are selected explicitly and do not silently fall back.

Both Study Agent prompts ask for evidence-supported mistake patterns, cautious treatment of user-provided and unverified references, a concrete next activity, a separate evidence-of-learning task with observable success criteria, and restraint against mastery claims from one answer. When there is no reference, the prompts prohibit claims of official alignment or invented curriculum mapping. Responses and task completion are not saved. Any future recorded learning evidence remains separate from `ReviewAttempt`, exam net, and XP; this is an explicit P2 backlog item.

No MEB curriculum text is bundled, copied, fetched, or redistributed. Reference notes are entered by the user and should be short paraphrases. Official background links: [MEB common text](https://tymm.meb.gov.tr/upload/brosur/2024programortakmetinOnayli.pdf), [MEB assessment guidance](https://tymm.meb.gov.tr/olcme-degerlendirme), and [current rollout plans](https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim). The official materials state All Rights Reserved; no open reuse license was identified during the scope review. Current national exams remain distinct from the phased curriculum model: [ÖSYM 2026 YKS schedule](https://www.osym.gov.tr/2026yks-basvurularin-alinmasi) and [MEB 2026 placement exam guide](https://www.meb.gov.tr/meb_iys_dosyalar/2026_04/03170012_LGS_Basvuru_ve_Uygulama_Kilavuzu_2026_.pdf). Hamartia's built-in exam and scoring model remains TYT/AYT/YKS-specific; the Study Agent is general-purpose and does not claim verified Maarif alignment.

## Verification

- `npm test` in `frontend/` — 18 passed.
- `npm run build` in `frontend/` — passed; Vite reports the existing large-chunk warning (>500 kB).
- `npm run test:docs` in `frontend/` with Nix Chromium — passed; English/Turkish guide navigation, default language, mobile width, handoff copy, and no external requests.
- `npm run test:browser` in `frontend/` with Nix Chromium and the temporary backend environment — passed. It exercised synthetic question creation/edit/search and existing settings/backup flows; output was `ai_included: false`, and an explicit assertion confirmed no `/study-agent/local` request.
- Targeted non-AI persistence/validation tests in `backend/` — 5 passed: legacy empty defaults, create persistence, URL rejection, update/clear semantics, and bounded insight summaries.
- `PYTHONPATH=. python benchmarks/benchmark_mixed_workloads.py` in `backend/` — passed with `ai_included: false`; the deterministic fixture includes three fictional curriculum references and checks full values and insertion order using an independent expected result.
- `npm test` in `desktop/` — 33 passed. ChatGPT provider behavior is mocked; no provider or model was contacted.
- `git diff --check` — passed.

The dedicated local question-analysis `OfflineModel` failure-path test was removed from `backend/tests/test_questions.py` for this phase's user requirement to exclude the local AI component from tests entirely. It was not run. No local-provider test, benchmark, endpoint request, or model call was made. The browser smoke uses only fictional records and its output keeps `ai_included: false`.

## Manual work still required

On the user's other computer, manually check a configured compatible endpoint with a fictional reference and prompt, then optionally check text and image question analysis. Separately verify ChatGPT desktop consent, selected model, response, sign-out, and revocation. The public English/Turkish guide has the steps; do not put secrets or real study content in reports/screenshots.
