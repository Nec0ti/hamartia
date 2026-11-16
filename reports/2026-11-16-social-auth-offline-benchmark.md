# Offline social-auth client benchmark

This benchmark measures the desktop social-auth client path without contacting Google or Firebase. It uses the installed Firebase JS SDK 13.3.0 against a fake Auth emulator-compatible HTTP endpoint bound to `127.0.0.1`, the real Google desktop OAuth callback handler with a mock browser callback and stub token exchange, and the real social IPC handlers with a loopback in-memory profile endpoint. No local AI or model is included.

## Reproduce

From `desktop/`:

```sh
npm ci --ignore-scripts
npm run bench:social-auth
```

On Linux x86_64 with Node v26.12.1, the benchmark completed with:

| Operation | Samples | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: |
| Google callback + Firebase credential exchange | 30 (after 5 warmups) | 4.250 ms | 11.257 ms | 11.659 ms |
| Profile PATCH + GET through desktop IPC | 48 (after 8 warmups) | 2.138 ms | 6.129 ms | 6.599 ms |
| Concurrent profile PATCH + GET through desktop IPC | 96 across 12 workers | 25.231 ms | 61.992 ms | 84.063 ms |

The run made 36 mock browser callbacks and Firebase credential exchanges, 72 Firebase endpoint requests, 152 profile PATCHes, and 154 profile GETs. The network guard permitted 57 TCP connections to numeric `127.0.0.1` only; it rejected other TCP/fetch destinations, DNS names, TLS sockets, and UDP. The benchmark checks OAuth PKCE/state callback behavior, Firebase token exchange and lookup, sign-in/sign-out and token clearing, complete private-profile shape, rejected identity leakage, every timed response, and the final concurrent profile state.

## Limits

Google's real provider latency, availability, consent UI, account restrictions, and OAuth token endpoint are not represented: the system-browser action is a mock callback and the OAuth token exchange is stubbed. Firebase availability and real provider credential acceptance are not represented: the real SDK speaks to a local fake Auth endpoint. The profile endpoint here is an in-memory fixture, so these client timings do not measure FastAPI or PostgreSQL. The separate PostgreSQL-backed profile API benchmark remains the database measurement. These local microbenchmark numbers are machine- and harness-specific, not production latency claims.

## Checks and CI

- `npm test --prefix desktop` — 56/56 passed.
- `npm run bench:social-auth --prefix desktop` — passed with the results above.
- `git diff --check` — passed.
- GitHub Actions runs the benchmark on its Linux package job after the existing desktop tests; other package checks remain unchanged.
