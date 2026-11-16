# Private forum submission quota

## Change

The PostgreSQL social repository now serializes submissions by verified UID with a transaction-scoped advisory lock, counts all submissions created in the preceding rolling hour, and inserts only while the count is below five. A rejected submission returns HTTP 429, a `Retry-After` header, and a structured `forum_rate_limit_exceeded` detail with the same retry seconds. Browser and Electron clients preserve that response and show a localized English/Turkish wait message.

The existing social/API and browser/Electron builds remain disabled by default. No schema migration or data conversion was needed. The limit does not remove existing pending or moderated rows; retry time is based on when the oldest of the five counted submissions leaves the hour window.

## Verification

- PostgreSQL 17.11 disposable loopback database: `backend/tests/test_social_forum.py` passed **8/8**, including the exact five/subsequent-sixth boundary, a submission after the one-hour window, structured retry timing, and 12-way concurrent oversubmission with exactly five stored rows.
- `node --test frontend/src/social/socialClient.test.js` — **7/7** passed; `node --test desktop/tests/socialIpc.test.cjs` — **9/9** passed.
- `npm test --prefix frontend` — **69/69** passed. `npm run build --prefix frontend` passed with the existing warning for a JavaScript chunk over 500 kB.
- `backend/benchmarks/benchmark_social_forum.py` passed against PostgreSQL 17.11 using synthetic identities and the existing loopback-only network guard. It checked 64 submissions across 13 synthetic authors, 24 more across five authors, and a separate five-accepted/sixth-rate-limited case. It observed one structured 429 with matching `Retry-After`; denial latency was **6.765 ms** in this run. Firebase calls: **0**; external network calls: **0**; fixture rows deleted.
- Python compilation and `git diff --check` passed.

These are local test/benchmark results, not production latency or hosting claims. No real Firebase account, provider credential, deployment, local AI, or home server was used. Agreement/legal/privacy, provider/API-host, network, security/lifecycle, and physical-host gates remain open.
