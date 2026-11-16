# Electron startup port-race readiness check

Date: 2026-11-16
Scope: ensure Electron accepts readiness only from the backend that received this launch's control token.

## Change

Electron now checks the existing data readiness endpoint, then calls `/desktop/ready` with its per-launch `X-Hamartia-Control-Token`. The desktop backend compares the token in constant time and responds with HTTP 204 plus `X-Hamartia-Control-Token-Verified: true` only after a match. Electron requires both the 204 status and that marker. An unrelated process returning HTTP 200 from the chosen port cannot satisfy this check. The shared readiness loop also covers a backend restart after backup restore. The regular `/healthcheck/ready` API contract and shutdown behavior are unchanged.

## Verification

- `PYTHONPATH=backend python -m unittest backend.tests.test_settings_api -v`: 15 passed, including missing, incorrect, and correct desktop readiness token cases. Run with the available Python 3.14 environment; repository CI uses Python 3.12.
- `node --test desktop/tests/*.test.cjs`: 75 passed, including an adversarial HTTP 200 response with no token-verification marker.
- `git diff --check`: passed.

No provider calls, local AI, server access, secrets, or deployment were used. No Electron package launch was performed; the modified main-process decision and backend route are covered by focused unit tests.
