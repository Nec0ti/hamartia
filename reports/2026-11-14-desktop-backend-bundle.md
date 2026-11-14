# Frozen Linux backend bundle verification

## Implemented slice

- Added `backend/desktop_server.py` as a PyInstaller entry point with loopback-only `HAMARTIA_HOST`, validated `HAMARTIA_PORT`, and `HAMARTIA_DATA_DIR` support.
- In packaged mode, serve the built Vite app from `_MEIPASS/frontend/dist`, including SPA fallback; `HAMARTIA_STATIC_DIR` remains available for source development.
- Added an Electron shell that launches the sidecar on an ephemeral loopback port, uses the current OS per-user application data path, and disables Node integration in a sandboxed, context-isolated renderer.
- Added an onedir PyInstaller spec and build helper that embed `frontend/dist`.

## Verification

- Linux PyInstaller onedir output: 63 MB.
- `python desktop/smoke_backend.py`: passed. It verified `/healthcheck/ready`, SPA fallback for `/study-plan`, referenced JS/CSS assets, API exam creation, and record persistence after a backend restart. Startup was 4,755.4 ms; `ai_included` was false.
- Backend tests at the sidecar implementation checkpoint: 84 passed.
- Frontend tests: 16 passed; Vite production build succeeded.
- `npm audit --omit=dev --prefix desktop`: zero production vulnerabilities. `npm audit --prefix desktop` reports six moderate `minimatch` advisories in Electron Builder's development-time dependency tree.

## Limits

Windows packaging, Debian/AppImage installer builds, and a full Electron UI launch have not yet been verified. Local Electron launch is blocked by the host's missing `libglib-2.0.so.0`; native Windows/Linux CI is being added. The in-app restore flow is pending; backup import must stop the sidecar and reuse the existing validated restore path before restarting it.
