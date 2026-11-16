# Electron backend readiness challenge proof

Date: 2026-11-16
Base: `origin/master` at `71c10624a70b89679a0a837a7afe83b0e7951cbc`

## Change

Electron now sends a fresh 256-bit nonce to `/desktop/ready`; the backend uses the per-launch control token as an HMAC-SHA256 key and returns a proof of that nonce. The token is never sent to the listener. Electron accepts only a 204 response with a valid 32-byte proof and compares it with Node's timing-safe buffer comparison. Readiness rechecks the spawned child after the request resolves, so an exited sidecar cannot pass based on a concurrent response.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend.tests.test_settings_api -v`: 15 passed.
- `node --test desktop/tests/backendReadiness.test.cjs`: 7 passed. Includes a real loopback fake server returning HTTP 204 plus the old public marker, mismatch and malformed proofs, retry nonce freshness, valid proof, late-proof timeout, and child exit during proof.
- `node --test desktop/tests/*.test.cjs`: 80 passed.
- `python -m py_compile backend/app/desktop.py backend/tests/test_settings_api.py` and `git diff --check`: passed.

No real provider, AI model, hosting server, or packaged Electron launch was used. The loopback server in the readiness test is a synthetic local fake.
