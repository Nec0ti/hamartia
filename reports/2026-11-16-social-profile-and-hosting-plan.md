# Social profile and home-hosting plan

**Status:** dated planning note accompanying a private social prototype. It is not legal advice, a compliance assessment, or launch approval. A social sign-in/profile UI prototype and a private moderated forum now exist; builds remain disabled by default. No public hosting, tunnel, live sign-in, or study-data sync is included. No legal or operational gate below is cleared. Forum implementation details and local verification are in [the forum report](2026-11-16-moderated-study-forum.md).

This concise planning note records the current implementation boundary and rechecks relevant primary sources as of 2026-11-16. Re-check primary sources and obtain qualified advice before any public launch.

## Confirmed project boundaries

- The current desktop/local JSON API remains separate, loopback-only, and unchanged. Social routes live in their own opt-in FastAPI service.
- Firebase is used for server-side verification of ID tokens. The UID comes from verified claims. A Google sign-in UI prototype exists, but builds are disabled by default and no live Firebase project, Google client, or social API host is configured.
- At the earlier profile-only checkpoint, PostgreSQL stored only the owner's optional profile fields and had no forum. The later forum adds the separate `social_forum_posts` table; details are in [the forum report](2026-11-16-moderated-study-forum.md). There is still no public profile HTTP route, direct messages, uploaded avatar, external avatar URL, or local-study-data sync.
- The profile has a nickname, integer age, grade, class, user-entered curriculum/preferences/goals, and a built-in avatar preset. There is no gender or date-of-birth field. Each field has an independent visibility switch that defaults off; the allowlisted public projection is not mounted over HTTP.
- Social profile data is not added to Study Agent payloads. No password is collected, stored, or sent.

The eventual host's operating system, capacity, storage health, network path, ISP limits, backup destination, restore performance, and availability have not been independently inspected. Whether Cloudflare Tunnel or another relay is selected/configured also remains unverified.

## Implemented profile slice

The isolated service now has owner-private `GET/PATCH /social/me/profile` routes backed by the additive `social_profiles` PostgreSQL table. Ownership uses only the UID derived from verified Firebase claims; no UID, email, or other claim can be mass-assigned or appears in the profile response. Updates use parameterized, per-column `INSERT ... ON CONFLICT` statements so concurrent partial changes to one account preserve unrelated fields. Authenticated responses set `Cache-Control: no-store`. The allowlisted visibility projection is tested as a pure function and is not mounted as an HTTP route. The new profile table has no legacy records to migrate; the local JSON data directory and desktop API are unchanged.

The separate service is opt-in and requires both `FIREBASE_PROJECT_ID` and `SOCIAL_DATABASE_URL`; `SOCIAL_HOST` must be a numeric loopback IP and defaults to `127.0.0.1`. It rejects hostnames and non-loopback addresses. Install `backend/requirements-social.txt`, apply migrations with `python -m app.social.migrate`, then start with `python -m app.social_server`. Database credentials belong in local environment/secret management only and must not be placed in source, this report, tests, or logs. The migration is additive and has no automated destructive downgrade; before future real-user data, define database backup/restore and rollback procedures.

## Dated 2026-11-16 sign-in/profile UI prototype

The optional bilingual UI has private profile onboarding, browser-dev Firebase popup support, and Electron system-browser OAuth using state, PKCE S256, and a one-use loopback callback. Electron keeps Google and Firebase tokens in main; browser development uses Firebase in-memory persistence. Both transports use fixed origins/routes, block redirects, and avoid local study API/auth changes. Packaged builds read a generated public config resource; missing values fail closed. Current builds contain no social provider configuration and emit an empty config, so sign-in is disabled.

An unchecked pre-auth acknowledgement is required in the app UI, and IPC/profile calls require the configured reviewed agreement version. The linked English/Turkish User Agreement pages are clearly marked draft and unapproved; no reviewed version is configured. This is only an app-level pre-auth acknowledgement gate. There is no server-side consent receipt or audit record, and a custom client can call Firebase Authentication and the social API outside the UI. The gate is not legal protection or a substitute for approved terms and qualified legal/privacy review. Before enabling real sign-in, resolve the agreement text/version, provider configuration, API host, legal/privacy review, and operational host/network gates.

The privacy guide describes this prototype without promising legal compliance. Social profile data is not included in Study Agent payloads. Google and Firebase provider behavior has not been verified with live credentials.

## Local verification snapshot

- Focused auth/profile/model/PostgreSQL integration tests passed: 23/23 against a temporary loopback PostgreSQL 17.11 cluster. They include two synthetic UIDs, default-private fields, strict age/text/avatar validation, unknown-field/UID/email rejection, verifier failures that prove storage is untouched, generic verifier/database errors, concurrent partial creates, nearest-rank percentile self-checks, and a route table without any public profile endpoint.
- Full backend unittest suite passed: 197/197 using that temporary PostgreSQL test database. Existing Python 3.14/httpx deprecation and temporary-file resource warnings appeared; no failures.
- PostgreSQL API benchmark passed on PostgreSQL 17.11 with 64 seeded synthetic rows, 64 independent full-profile oracles, 384 timed GETs, 384 timed PATCHes, and 12 concurrent workers issuing 288 calls. Percentiles use nearest-rank `ceil(p*n)-1`; a 24-value self-check verifies p99 selects the maximum. GET latency was p50 3.975 ms / p95 7.928 ms / p99 8.770 ms; PATCH p50 7.434 ms / p95 10.575 ms / p99 12.002 ms; concurrent-call p50 49.323 ms / p95 70.881 ms / p99 78.579 ms. The pool opened 9 of 12 allowed connections and reported no waiters; benchmark-process peak RSS was 1,313,748 KiB for this run (process-wide TestClient harness peak, not an isolated server measurement). These are local TestClient + loopback-PostgreSQL measurements, not service performance claims.
- Firebase verifier tripwire and loopback-only socket guard passed: zero Firebase calls and zero external network calls. The benchmark refuses non-PostgreSQL or non-loopback database URLs and never substitutes SQLite or a fake repository.
- Backend CI requires a dedicated PostgreSQL 17 service for the integration tests and benchmark, so the database-backed checks cannot silently fall back to SQLite or mocks.

## Data and provider boundary

| Information | Planned location or processing | Current status |
| --- | --- | --- |
| Local exams, mistakes, practice, and progress | Existing per-user desktop data directory | Remains local; no migration or sync |
| Social profile | PostgreSQL on a future operator-controlled host | Private owner-scoped prototype only |
| Account identity | Firebase Authentication/Admin verification | Disabled UI prototype plus token verification boundary; no live project or credentials |
| Study Agent request | Existing explicitly initiated provider flow | Profile and forum context stay excluded by default |
| Public profile projection | Allowlisted values with explicit per-field opt-in | Pure function tested; no public endpoint |

Google/Firebase identity and any eventual reverse proxy are separate processors from the home database. Do not promise that all processing occurs at home if a third-party identity or edge service is used. The current code is loopback-only and does not configure Cloudflare.

## Hosting and privacy facts to carry forward

Cloudflare documents Tunnel as an outbound-only connection that does not require a public IP, with traffic to the origin flowing through Cloudflare’s network. Its current HTTP privacy documentation describes TLS termination and request inspection at Cloudflare’s edge, with request/response processing in memory. If Tunnel is selected, Cloudflare is part of the data-processing path; tunnel encryption does not prevent edge processing of plaintext. Decide whether that is acceptable, document it accurately, bypass caching on every authenticated route, and verify actual cache behavior before any deployment. These are design gates, not claims that a tunnel exists or is configured.

The existing desktop API must not be rebound to a LAN/public interface or have its JSON data directory exposed. PostgreSQL must remain private to the service network. Before any public host, test HTTPS and authenticated-route cache behavior, minimize/redact logs, use a least-privilege database role, encrypt backups, and prove a restore from a physically separate failure domain. A single storage device does not establish redundancy or backup safety.

## Legal and launch gates — all open

1. **User Agreement and privacy notice:** the bilingual `v0.1-draft` User Agreement is a review placeholder, not approved terms. Obtain qualified legal/privacy review, complete and version both notices against the real processor/hosting path, and configure no reviewed version until that work is done. There is no server-side consent receipt/audit record; the UI acknowledgement can be bypassed by a custom client.
2. **Türkiye and operator status:** obtain written advice about KVKK duties, data-controller identity, notices, rights, retention/deletion, cross-border transfers, and any applicable registry obligations. KVKK describes a controller as a real or legal person determining processing purposes and means; this does not decide how this specific service is classified or whether a legal entity is required.
3. **5651 and community scope:** obtain counsel/BTK confirmation about current Law No. 5651, any hosting-provider duties, contact/notice handling, traffic-information obligations, and whether a future study app with social features falls within relevant social-network rules. The Ministry of Justice consolidated entry now reflects later amendments; the older 2023 BTK procedure contains a conditional treatment for services where social interaction is secondary, but neither source alone classifies Hamartia or settles its obligations.
4. **Children and intended jurisdictions:** decide intended audience and age handling with qualified counsel. Self-entered age is unverified. Review child privacy, consent, safety, and platform duties in each intended jurisdiction before collecting real profiles or opening registration.
5. **Cloudflare:** decide whether Cloudflare’s edge processing is acceptable and disclose it if used; otherwise choose another access design and re-evaluate its providers and risks.
6. **Physical host:** inspect current OS updates, CPU/RAM headroom, disk SMART/free-space status, power protection, firewall, network path, and existing services. Run a representative low-traffic load test and demonstrate encrypted, offline, physically separate backup restoration. A tunnel does not solve host capacity, reliability, or legal duties.
7. **Security and lifecycle:** before real users, review owner isolation across every route and background job, credential rotation, logging, retention, profile export/deletion, incident response, and a fast disable/rollback plan. Public visibility remains off unless a user explicitly selects each field.

Until these gates are decided and completed, keep this service private and loopback-only. The UI prototype remains disabled. The forum has authenticated reads for approved posts only; pending content is available only to configured moderators, except that a submitter receives a pending-status receipt. Study-data sync remains a separate implementation slice. Public profile reads must remain closed. DMs remain deferred. No public deployment or real-user data is part of this PR.

## Primary references checked for this update

- [Firebase Admin ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens) — server-side token verification and UID.
- [Google OAuth for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app) — installed apps are public clients and must not keep a client secret; used for implementation guidance only.
- [Firebase Google sign-in](https://firebase.google.com/docs/auth/web/google-signin), [Firebase Auth persistence](https://firebase.google.com/docs/auth/web/auth-state-persistence), and [Firebase Auth Emulator](https://firebase.google.com/docs/emulator-suite/connect_auth) — SDK flow and offline test guidance; no live provider verification was run.
- [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/) — outbound-only tunnel and request path through Cloudflare.
- [Cloudflare Default HTTP Privacy](https://developers.cloudflare.com/data-localization/regional-services/http-requests/) — TLS termination, inspection, and in-memory edge processing.
- [Cloudflare cache controls](https://developers.cloudflare.com/cache/concepts/cache-control/) and [authenticated/dynamic content guidance](https://developers.cloudflare.com/cache/troubleshooting/dynamic-content-and-login-issues/) — cache behavior must be verified in the actual configuration.
- [KVKK: Who is the Data Controller?](https://www.kvkk.gov.tr/Icerik/2032/Veri-Sorumlusu-Kimdir) and [KVKK: transfers abroad](https://www.kvkk.gov.tr/Icerik/2053/Yurtdisina-Aktarim) — primary authority background; counsel must assess the actual processing.
- [Ministry of Justice UYAP consolidated Law No. 5651](https://mevzuat.adalet.gov.tr/mevzuat/103224?query=5651) — current consolidated law; this note does not interpret its application to Hamartia.
- [BTK Board Decision 2023/DK-İD/119 and Social Network Provider Procedures](https://www.btk.gov.tr/kurul-kararlari?search=sosyal+a%C4%9F+sa%C4%9Flay%C4%B1c%C4%B1) — official procedure and decision. The old direct PDF link from the branch memo returned 404 during this check; BTK’s official search result exposes the procedure.
- [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), [FTC COPPA guidance](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions), and [UK ICO Children’s Code](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/) — jurisdictional starting points only, not applicability determinations.
