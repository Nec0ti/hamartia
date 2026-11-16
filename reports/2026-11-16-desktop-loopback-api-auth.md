# 2026-11-16 desktop loopback API authentication

## Change

The desktop backend now requires the per-launch 256-bit control token for every request except readiness (`/healthcheck/ready`, `/desktop/ready`) and graceful shutdown (`/desktop/shutdown`, which already checks the token itself). A missing backend token fails closed with `503`; a missing or incorrect request token returns `401`. The desktop server requires a configured token. The direct development ASGI entry point allows tokenless local use only when Electron did not configure a token; when Electron starts it, the same guard applies.

Electron keeps the random token in its main process and passes it to the backend through the existing child environment. It installs the value as an `HttpOnly`, `SameSite=Strict` cookie scoped to the exact loopback backend URL before loading the renderer. Renderer JavaScript and preload/IPC receive no token value. The ChatGPT main-process client sends the existing control-token header for all of its local backend reads and draft previews. Restart and backup restore reuse the running Electron process's same token; backups include only the backend data directory, and the token is not stored in settings or logged.

## Threat scope and limits

This prevents a different unprivileged OS account on the same machine from scanning the random loopback port and reading the question or backup APIs without the per-launch token. Origin checks remain in place for browser writes, but no `Origin` header is not treated as authentication. Readiness remains public and returns no study data. The local dev API remains unauthenticated only when started directly without `HAMARTIA_CONTROL_TOKEN`; this compatibility path is not used by Electron, which always generates and supplies a token.

This does not protect against the same OS account, an administrator/root user, malware running as the app user, or arbitrary code execution in the trusted renderer. The packaged Electron smoke requires the renderer to read the protected API through its cookie and confirms the cookie is not exposed to JavaScript; this passed in Windows and Linux package CI. The backend unit tests verify cookie/header validation, while CI verifies Electron's cookie behavior on both platforms. No AI/provider path, benchmark, social/legal content, deployment, or server data was involved; an auth-throughput benchmark is not applicable to this request.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest backend.tests.test_settings_api backend.tests.test_dev_origin_guard -v`: 17 tests passed. The regression checks absent and wrong credentials on originless `/questions` and `/backup`, fail-closed missing configuration, valid main-process header, packaged cookie, trusted Vite-origin cookie, and existing hostile-origin behavior.
- Full backend suite: 314 tests run, 302 passed, and 12 PostgreSQL integration tests skipped because `HAMARTIA_SOCIAL_TEST_DATABASE_URL` was not configured; these tests use mocks and no provider/local AI call was made.
- `npm test` in `desktop`: 81 tests passed. Mocked ChatGPT flows assert every local backend request carries the main-process control header.
- `node --check main.cjs`, `node --check chatgpt.cjs`, and `node --check smoke_electron.cjs`: passed.
- `git diff --check`: passed.
- Packaged smoke requires an authenticated `/questions` response from renderer JavaScript and confirms `document.cookie` cannot read the control cookie. Windows and Linux package CI both passed; no local AI or provider was called.
- First PR #60 package run failed on both Windows and Linux in the preexisting frozen-backend smoke: it started the now-strict packaged backend without `HAMARTIA_CONTROL_TOKEN`, then fetched `/study-plan` without authentication and received the expected `503`. This was a shared smoke-harness setup issue, not a platform-specific failure. The smoke now creates a random synthetic token, asserts originless `/questions` and `/backup` requests return `401`, and authenticates static/API requests and the persistence check with that token. Follow-up PR run 43921567813 passed on Linux (3m27s) and Windows (4m46s), including the packaged Electron cookie/API smoke on both platforms and Windows installer smoke.
