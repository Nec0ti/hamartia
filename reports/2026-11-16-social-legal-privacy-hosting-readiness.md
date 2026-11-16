# Social prototype legal, privacy, and hosting readiness

**Status:** Internal source review only; not legal advice, an implementation review, or launch approval. All launch gates remain open. Source pages were accessed on 2026-11-16 unless a publication/update date is stated below. This report reflects the code and planning records at master `5b569c0723ca9f43b4dd5ae9a376d8001e161709` (ARETE-062).

## Current dataflow and boundary

| Flow | Current-master evidence | Readiness limit |
| --- | --- | --- |
| Account sign-in | Optional Google sign-in UI exchanges credentials for Firebase Authentication. Electron keeps tokens in the main process; browser development uses in-memory persistence. Builds are disabled without public Firebase/API settings and a reviewed agreement version. | No live Google/Firebase project, credentials, or sign-in was inspected or used. |
| Identity verification | The separate social API verifies Firebase ID tokens and derives the account UID from verified claims. | The API is loopback-only in the prototype. Its eventual public origin and provider configuration are unconfigured. |
| Profiles | PostgreSQL `social_profiles` stores owner-scoped nickname, self-entered age, grade, class, user-entered curriculum/preferences/goals, avatar preset, and field visibility settings that default private. | No public profile HTTP route exists. No profile or account deletion/retention policy is set. |
| Forum | PostgreSQL `social_forum_posts` stores bounded title/body, verified author UID, pending/approved/rejected status, and moderation state. Reads require sign-in and return approved content; moderator queue/actions are restricted by server-configured UIDs. | A user may nevertheless include personal or sensitive details in free text. No real user content exists. |
| Local study data and AI | The desktop/local API and local study records remain separate; social profile/forum data are not included in Study Agent requests. | No social-to-study sync, public launch, or AI/provider execution is part of this work. |
| Proposed external path | If Firebase Authentication is used, Google documents that Firebase Authentication runs only from US data centers. A future Cloudflare Tunnel would put Cloudflare between users and the home origin. | No tunnel, API host, production routing, cache policy, provider contract, or current host configuration was inspected. |

The relevant implementation records are [the social profile/hosting plan](2026-11-16-social-profile-and-hosting-plan.md), [sign-in prototype](2026-11-16-social-signin-onboarding.md), and [moderated forum report](2026-11-16-moderated-study-forum.md). These describe a private opt-in prototype, not a live service.

## Turkish personal-data rules

Law No. 6698 applies to processing personal data by natural or legal persons, with the statute covering automated processing and certain non-automated processing in a filing system. It defines the controller by who determines purposes and means, and the processor by processing on a controller’s behalf. KVKK guidance treats decisions about collected fields, purpose, access, and retention as relevant to controller identification. The operator’s actual role must be assessed from real decisions and contracts; Google/Firebase or a future host cannot be assigned a role solely by product name. See [Law No. 6698, Articles 1–5 and 10–16](https://www.kvkk.gov.tr/Icerik/6649/Personal-Data-Protection-Law) (official KVKK English translation; Turkish original controls) and [KVKK decision 2020/71](https://www.kvkk.gov.tr/Icerik/6874/2020-71).

The statute requires specified, explicit, legitimate purposes; proportionate data; and retention for the period required by law or purpose. It also provides notice and data-subject rights and requires appropriate technical and organizational security measures. Where processing grounds end, data must be erased, destroyed, or anonymized, subject to other applicable laws. This means a retention/deletion policy must cover accounts, profiles, posts and moderation records, logs, backups, and provider-held data; the sources do not supply a one-size-fits-all duration for this service. See [Law No. 6698](https://www.kvkk.gov.tr/Icerik/6649/Personal-Data-Protection-Law) and [KVKK deletion guidance](https://www.kvkk.gov.tr/Icerik/2038/kisisel-verilerin-silinmesi-yok-edilmesi-veya-anonim-hale-getirilmesi).

The no-monetization/no-advertising plan does not itself establish an exemption. The reviewed provisions contain no general hobby/no-revenue exclusion from the Law’s substantive requirements. This is not a conclusion about entity formation, tax status, or whether a legal entity is required; those are separate questions for Turkish legal/accounting professionals.

## International processing and provider roles

Firebase’s [privacy and security page](https://firebase.google.com/support/privacy) (last modified 2026-09-24) says Firebase Authentication is run only from US data centers. It identifies email, IP address, and user-agent information among Authentication data, and says logged IPs are kept for a few weeks. Firebase states that other services may process/store data globally unless a service provides and the customer selects a location. Its [Data Processing and Security Terms](https://firebase.google.com/terms/data-processing-terms) allow customer data to be processed in countries where Google or subprocessors maintain facilities, subject to applicable location commitments; they also place customer-side data-subject and applicable incident-notification duties on the customer.

KVKK’s [current international-transfer guidance](https://www.kvkk.gov.tr/Icerik/2053/Yurtdisina-Aktarim) describes the amended Article 9 framework: a Board adequacy decision, an applicable statutory safeguard, or a narrowly specified occasional-transfer exception. The page states that no adequate-protection countries had been designated as of this review. The actual Firebase processing, contractual terms, transfer path, and available Turkish-law safeguard require qualified review. A home-hosted PostgreSQL database would not by itself localize authentication or any enabled edge/provider processing.

Cloudflare’s [Tunnel log documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/monitor-tunnels/logs/) (last updated 2026-09-29) says `cloudflared` server logs go to stderr and are not persisted by default, while logs can be streamed through the dashboard or saved locally. This does not establish what Cloudflare retains for this account, the fields exposed by enabled services, or contractual roles. The exact plan, features, privacy/DPA terms, cache behavior, and data path must be reviewed if Cloudflare is chosen.

## VERBİS is a separate conditional question

VERBİS registration is not the same question as whether substantive KVKK rules apply. Law No. 6698 Article 16 permits Board-set exceptions. The 2025/1572 decision sets conditional employee-count, balance-sheet, and main-activity thresholds. A later 2025/2393 decision, dated 2025-12-25 and reflected in KVKK’s [implementation notice](https://www.kvkk.gov.tr/Icerik/8577/kisisel-verileri-koruma-kurulunun-04-09-2025-tarihli-ve-2025-1572-sayili-kararinin-uygulama-esaslarina-iliskin-kamuoyu-duyurusu), clarifies that where a controller does not keep balance-sheet books and has no annual balance-sheet total, only the employee-count criterion is used for this exception analysis. The actual operator, bookkeeping method, headcount, and whether the main activity involves special-category data are unknown. Do not infer registration status from “solo hobby project.”

## 5651 and child-service classification

BTK’s [Board Decision 2023/DK-İD/119 and attached Social Network Provider Procedures](https://www.btk.gov.tr/uploads/boarddecisions/sosyal-ag-saglayici-hakkinda-usul-ve-esaslar/119-06-sosyal-ag-saglayici-hakkinda-usul-ve-esaslar-28-03-2023-id.pdf), dated 2023-03-28, define a social network provider as a real or legal person enabling users to create, view, or share content for social interaction. The rules exclude certain services where social interaction is limited to part of a publication or secondary to another service, and state that social-network-provider duties do not remove content/hosting-provider duties. Some listed duties apply above one million daily accesses from Türkiye. Whether a forum-centered Hamartia service fits a category, and which other current Law No. 5651 duties apply, is unresolved. The current consolidated [Law No. 5651](https://mevzuat.adalet.gov.tr/mevzuat/103224?query=5651) and amendments must be reviewed by counsel; the home server’s CGNAT status does not determine these legal classifications.

**New child-services rule — applicability and timing unresolved.** The Official Gazette published the [Regulation on Child-Specific Services and Age Verification by Social Network Providers](https://resmigazete.gov.tr/eskiler/2026/10/20261010-15.pdf) on **2026-10-10**, issue 33396. Its scope covers domestic or foreign social-network providers accessible from Türkiye (Article 2), and it defines a child as someone under 18 (Article 4). Conditionally, **if Hamartia is a social network provider within this regulation**, its text says:

- providers may not serve children under 15 (Article 5);
- at account creation, age must be verified using the age token process; the regulation describes an e-Devlet token containing only whether a user is 15+ and, if so, 18+ (Articles 6–7);
- users aged 15–17 must receive a differentiated service, including default high privacy, age-appropriate presentation, and listed restrictions on public profiles, messaging, recommendations, and other features (Article 8); and
- parental-control and Turkish-language appeal mechanisms are required (Articles 9–10).

The regulation’s Article 13 says it enters into force on **2026-01-01**, a date that predates its publication by more than nine months. Article 1–2 do not make a hobby/no-advertising carve-out apparent, but Hamartia’s classification and the stated effective date’s legal effect need a Turkish lawyer’s assessment. These provisions are reported conditionally, not applied as a legal conclusion.

Google’s [account age policy](https://support.google.com/accounts/answer/1350409) says the minimum age to independently manage a Google Account is 13 in countries not specially listed. That provider account rule does not settle Hamartia’s own age, consent, child-safety, or service-classification questions.

## Hosting and operational unknowns

The proposed origin is a 4 GB Ubuntu home server behind CGNAT, but no live server, ISP, network, Cloudflare account, or configuration was inspected. Its OS patch level, CPU/memory headroom, disk health, firewall, backups, restore path, uptime, power protection, and log retention are unknown. A tunnel can provide reachability through a provider; it does not establish data locality, origin security, backup resilience, legal compliance, or acceptable capacity. Before any live users, the host design and failure recovery must be assessed against the real service path.

## Decisions and open launch gates

The user must decide the intended audience and age floor; invite-only/private versus public access; retention and deletion rules for accounts, profiles, posts, moderation, logs, and backups; and whether to use the home server, Cloudflare Tunnel, or a different hosting/provider path. The legal documents, provider/API configuration, and deployment remain unapproved/unconfigured.

Before enabling sign-in, collecting real user data, or public launch, keep these gates open pending qualified review and evidence:

1. Turkish counsel: controller/operator identity, KVKK bases/notices/rights/security/breach handling, transfer safeguards, VERBİS analysis, Law No. 5651 classifications/obligations, child-rule scope, and its publication/effective-date discrepancy.
2. Provider review: actual Firebase, Google OAuth, Cloudflare, subprocessors, contracts, data regions, retention, access logging, and cross-border transfers.
3. Product decisions: target audience, age handling, public/private access, moderation and user-report handling, and a deletion/retention schedule.
4. Hosting review: inspect the actual origin, network path, TLS/cache/access controls, operational logs, and backup/restore in the selected design.
5. Separate professional advice on whether any business/entity registration, tax, or other operator formalities apply. No company formation or tax exemption is asserted here.

No gate is marked complete by this report. No agreement/privacy text is approved, and the social build must remain disabled pending the existing gates. No live configuration or server was inspected; no provider contact, credential use, deployment, or legal implementation was performed.

## Official primary sources checked

- KVKK, [Law No. 6698, English translation](https://www.kvkk.gov.tr/Icerik/6649/Personal-Data-Protection-Law), ratified 2016-03-24; published in Official Gazette 2016-04-07. Accessed 2026-11-16. Turkish text controls.
- KVKK, [international transfer guidance](https://www.kvkk.gov.tr/Icerik/2053/Yurtdisina-Aktarim), reflecting Article 9 amendments effective 2024-06-01. Accessed 2026-11-16.
- KVKK, [deletion/destruction/anonymization guidance](https://www.kvkk.gov.tr/Icerik/2038/kisisel-verilerin-silinmesi-yok-edilmesi-veya-anonim-hale-getirilmesi). Accessed 2026-11-16.
- KVKK, [VERBİS implementation notice](https://www.kvkk.gov.tr/Icerik/8577/kisisel-verileri-koruma-kurulunun-04-09-2025-tarihli-ve-2025-1572-sayili-kararinin-uygulama-esaslarina-iliskin-kamuoyu-duyurusu), covering 2025/1572 (2025-09-04) thresholds and the later 2025/2393 (2025-12-25) bookkeeping clarification. Accessed 2026-11-16.
- BTK, [Decision 2023/DK-İD/119 and Social Network Provider Procedures](https://www.btk.gov.tr/uploads/boarddecisions/sosyal-ag-saglayici-hakkinda-usul-ve-esaslar/119-06-sosyal-ag-saglayici-hakkinda-usul-ve-esaslar-28-03-2023-id.pdf), dated 2023-03-28. Accessed 2026-11-16.
- Resmî Gazete, [Child-Specific Services and Age Verification Regulation](https://resmigazete.gov.tr/eskiler/2026/10/20261010-15.pdf), published 2026-10-10, issue 33396; Article 13 states 2026-01-01 effective date. Accessed 2026-11-16.
- Ministry of Justice, [consolidated Law No. 5651](https://mevzuat.adalet.gov.tr/mevzuat/103224?query=5651). Accessed 2026-11-16.
- Google, [Firebase privacy and security](https://firebase.google.com/support/privacy), last modified 2026-09-24; [Firebase Data Processing and Security Terms](https://firebase.google.com/terms/data-processing-terms). Accessed 2026-11-16.
- Google, [Google Account age requirements](https://support.google.com/accounts/answer/1350409). Accessed 2026-11-16.
- Cloudflare, [Tunnel log documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/monitor-tunnels/logs/), last updated 2026-09-29. Accessed 2026-11-16.

**Verification:** `python3 scripts/benchmark_docs.py --output /tmp/hamartia-social-legal-readiness-docs.json` passed: 17 rendered routes per locale, 818 local links/assets, zero errors, and no network or AI access. The release publisher parsed the live PR body’s marked bilingual summary with all six fields in each language; `python3 .github/scripts/test_release_metadata.py` passed 6/6. `git diff --check` passed after editing. No application tests or live-service checks were run; this is a documentation-only change.
