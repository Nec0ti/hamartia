# 2026-11-16 desktop readiness probe privacy review

## Finding and change

The desktop control-token middleware deliberately leaves `GET /healthcheck/ready` unauthenticated so Electron launchers and smoke checks can detect readiness. The route previously returned the absolute local data directory on success and `str(exc)` on failure. Any local loopback caller could therefore learn the user's filesystem path and, when storage failed, receive filesystem error details without the control token.

The readiness response now contains only `{"status":"ready"}` on success. Storage failure returns HTTP 503 with the existing `not_ready` status and generic `Data storage is unavailable.` message. Returning a non-2xx status matters because all in-repository launch/readiness callers gate on HTTP success; the previous 200 response could let them proceed with unusable storage. The route remains unauthenticated, and the separate liveness endpoint is unchanged.

## Security review scope

Static review at GitHub `master` commit `6c5a90135784d8f1dbf18cc3da87b908ab96d5c7` covered desktop loopback token and origin guards, Electron preload/IPC boundaries, local settings and credential handling, upload validation and image-path resolution, JSON storage permissions and symlink checks, backup snapshot/export/archive validation, restore journaling/recovery, social authentication request boundaries, and all in-repository readiness callers. The readiness disclosure and failure-status contract above were the only confirmed issues in this focused review. No other finding was confirmed from source inspection.

The review did not run a dynamic penetration test, race stress test, packaged-app smoke, or external social-service test. The noted exposure required a caller able to reach the local loopback port; it did not disclose record contents or credentials.

## Verification

`PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend/tests/test_healthcheck.py -v` passed 2/2. The regression checks the endpoint remains available without a control token, excludes the data path from the success response, and returns HTTP 503 with generic failure details without exposing the data path or raw exception text.
