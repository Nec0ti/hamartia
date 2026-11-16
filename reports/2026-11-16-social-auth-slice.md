# Social authentication boundary prototype

Status: implemented as an isolated, private, data-free prototype. This is not a public launch or a user account system.

## Scope and boundary

- `backend/app/main.py` and the local desktop API are unchanged. The opt-in service runs separately with `python -m app.social_server` from `backend/` after installing `backend/requirements-social.txt`.
- `FIREBASE_PROJECT_ID` is required. `SOCIAL_HOST` defaults to `127.0.0.1` and rejects non-loopback values; `SOCIAL_PORT` defaults to `8765`.
- The only mounted routes are `GET /social/health` and `GET /social/me`. The latter accepts a case-insensitive Bearer scheme, checks signature, expiry, and revocation through Firebase Admin, then independently binds audience and issuer to the configured project and accepts a nonempty UID of at most 128 characters. Invalid, expired, revoked, and disabled-account tokens return generic 401; Firebase verifier outages return generic 503. Its success response is only `{"uid":"..."}`.
- No email, profile, local study data, datastore, Google client login, AI/provider execution, or deployment/tunnel path is part of this slice. SDK verification is dependency-injected and tests use deterministic mocks.

## Verification

- Focused tests: `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend.tests.test_social_auth` — 13/13 passed. Coverage includes missing/malformed, case-insensitive bearer scheme, expired, revoked, disabled account, verifier outage, wrong-project/audience, wrong issuer, invalid UID, UID-only response, required project config, loopback binding, SDK revocation/error classification, and route isolation.
- Full existing backend suite: `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests` — 187/187 passed. The suite emits existing Python 3.14 deprecation/resource warnings.
- Adversarial oracle/benchmark: `PYTHONPATH=backend:backend/benchmarks /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_social_auth.py` — eight independent expected outcomes passed at 100 repeats each. A fail-fast Firebase verifier tripwire and socket `connect`/`connect_ex` guards reported zero Firebase and network calls. Per-request timings are local TestClient timings, not production latency claims.
- `git diff --check` — passed.

## Launch gates

Keep the service private. Before any public launch, separately complete legal/privacy review, a Cloudflare/network architecture and access-control review, and physical-host hardening and operational review. Then conduct an explicitly authorized live Firebase check with test credentials on an isolated device; never put credentials or tokens in the repository, tests, reports, or chat. These gates are not completed by this prototype.
