# Private moderated study forum

**Status:** implemented as an opt-in prototype on the separate social service. Builds remain disabled unless the existing provider/API configuration and reviewed-agreement version are supplied. This is not a public launch, legal review, or readiness claim.

## Slice and access rules

- `POST /social/forum/posts` accepts only a bounded title and body. The API derives `author_uid` only from the verified Firebase token's `sub` claim, stores the post as `pending`, and returns only its ID and pending state. Caller-supplied UID, author, role, status, moderator, and unknown fields are rejected.
- `GET /social/forum/posts` requires a verified bearer token and selects only `approved` posts. Rejected and pending content is not returned from this route. Authenticated responses use `Cache-Control: no-store`; lists are bounded to 1–100 rows.
- `GET /social/forum/moderation` and `PATCH /social/forum/posts/{id}/moderation` require a UID listed in server-only `SOCIAL_MODERATOR_UIDS`. Empty or missing configuration grants no moderators. The client cannot self-assign or supply a role. A moderator's own pending submissions are omitted from their queue, and direct attempts to approve or reject them return 403.
- Moderation permits only `approved` or `rejected`, and only while the row remains `pending`. PostgreSQL `SELECT ... FOR UPDATE` serializes decisions; concurrent reviewers cannot overwrite the first final state. The queue and feed omit author/moderator UIDs. Rejected content has no read endpoint.
- The signed-in profile modal provides a bilingual approved-post feed and post form with a pending-approval confirmation. It shows moderator actions only after the protected queue request succeeds; the server remains authoritative. Browser and Electron clients use fixed route paths, the existing agreement gate, the in-memory Firebase session, no-store fetches, and blocked redirects.
- The local JSON desktop API, profile table, Study Agent payloads, and local study records are unchanged. No direct messages, search, reactions, public profile pages, study-data sync, real provider credentials, or deployment were added.

## Database change and rollback

Migration `002_moderated_forum.sql` adds the forum table, status constraints, and partial indexes. Migration `001_profiles.sql` and existing profile rows are unchanged. The change is additive and needs no data conversion. Rollback means turning off the UI/social routes and retaining the migration and forum rows; do not drop the table or delete records to roll back. If the feature is ever used with real data, define and test a database backup/restore procedure before deployment.

## Verification

- Disposable PostgreSQL 17.11 UTF-8 on `127.0.0.1:55432`: full backend suite **202/202 passed**, including forum identity spoofing, role gates, self-moderation, approved-only reads, hidden rejected/pending content, bounded lists, concurrent decisions, existing profile owner isolation, and migration idempotence. Focused social auth/profile/forum tests **28/28 passed**.
- Frontend tests **59/59 passed**; Electron tests **64/64 passed**; Vite production build passed with the existing warning for a JavaScript chunk over 500 kB. CI now installs desktop test dependencies and runs those tests, and has a required PostgreSQL 17 service for backend tests and benchmarks.
- The offline API benchmark used 64 synthetic submissions (32 approved, 32 rejected), 64 repeated approved-feed correctness reads, and 24 further submissions moderated concurrently by 8 workers. It checked pending-only submission responses, moderator identity omission, exact approved content, rejection exclusion, final database counts, and fixture deletion. Percentiles use nearest-rank `ceil(p*n)-1`.

| Operation | Samples | p50 | p95 | p99 | Mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| Submit | 64 | 8.639 ms | 12.948 ms | 40.166 ms | 9.392 ms |
| Moderate (sequential) | 64 | 10.224 ms | 13.313 ms | 15.682 ms | 9.932 ms |
| Approved feed | 64 | 5.374 ms | 9.118 ms | 10.034 ms | 5.843 ms |
| Concurrent moderation | 24 across 8 workers | 61.721 ms | 89.326 ms | 111.907 ms | — |

Concurrent moderation completed in **202.637 ms** total in this run. These are local FastAPI TestClient plus loopback PostgreSQL measurements, not production latency claims. Firebase SDK calls were guarded to zero; socket guards allowed only the loopback PostgreSQL endpoint and reported zero external network calls. The synthetic rows were deleted.

The documentation/browser smoke command could not launch Chromium locally because `libglib-2.0.so.0` is unavailable in this NixOS environment. CI installs the Playwright system dependencies and runs the existing browser checks; no real social-provider UI session was performed.

No real Firebase sign-in, real user data, local AI, public API, tunnel, home server, or production launch was used. Existing agreement/legal/privacy, provider/API-host, network, security, physical-host, and manual sign-in gates remain open; this report does not claim broader launch readiness.
