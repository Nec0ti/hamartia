# 2026-11-16 desktop readiness probe privacy review

## Finding and change

The desktop control-token middleware deliberately leaves `GET /healthcheck/ready` unauthenticated so Electron launchers and smoke checks can detect readiness. The route previously returned the absolute local data directory on success and `str(exc)` on failure. Any local loopback caller could therefore learn the user's filesystem path and, when storage failed, receive filesystem error details without the control token.

The readiness response now contains only `{"status":"ready"}` on success. Failure keeps the existing `not_ready` status and returns the generic `Data storage is unavailable.` message. The route remains unauthenticated; Electron and launcher callers only need the HTTP success status. The separate liveness endpoint is unchanged.

## Security review scope

Static review at GitHub `master` commit `6c5a90135784d8f1dbf18cc3da87b908ab96d5c7` covered desktop loopback token and origin guards, Electron preload/IPC boundaries, local settings and credential handling, upload validation and image-path resolution, JSON storage permissions and symlink checks, backup snapshot/export/archive validation, restore journaling/recovery, and social authentication request boundaries. The readiness path disclosure above was the only confirmed issue in this focused review. No other finding was confirmed from source inspection.

The review did not run a dynamic penetration test, race stress test, packaged-app smoke, or external social-service test. The noted exposure required a caller able to reach the local loopback port; it did not disclose record contents or credentials.

## Verification

`PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend/tests/test_healthcheck.py -v` passed 2/2. The regression checks the endpoint remains available without a control token, excludes the data path from the success response, and excludes both the data path and raw exception detail from the failure response.
