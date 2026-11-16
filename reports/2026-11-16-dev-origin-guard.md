# Local development API origin guard

## Change

`scripts/dev.py` now launches `app.dev:application`, an ASGI wrapper around the shared `app.main:app` using the existing `DesktopOriginGuard` and `desktop_allowed_origins()`. The guard rejects browser write requests from hostile origins before FastAPI parses multipart request bodies. The configured localhost and loopback Vite origins remain allowed. Production and direct-test imports of `app.main:app` are unchanged, as is the desktop server setup.

## Verification

Command:

```text
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p 'test_dev_origin_guard.py' -v
```

Result: 1 test passed. Using the actual dev ASGI target, a hostile-origin multipart question upload returned 403 and left both `questions.json` and `uploads/` absent. A multipart upload from `http://localhost:5173` returned 201 and persisted one question and one image. No provider, local AI, or external service was accessed.

## Limits

This focused test exercises the ASGI target configured in `scripts/dev.py`; it does not spawn Uvicorn or Vite as subprocesses. PR CI and desktop package jobs are still required before merge.
