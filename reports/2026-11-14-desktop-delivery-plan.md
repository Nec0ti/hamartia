# Desktop packaging and release automation plan

## Product requirements

- Ship a Windows 10/11 installer, Debian `.deb`, and Linux AppImage.
- Store persistent records under the operating system's per-user application data directory.
- Bind the local API to loopback and serve the bundled React app from an HTTP origin.
- Build each platform on a native GitHub Actions runner and verify installation, launch, and data persistence.
- For every merged PR after release automation is installed, publish one GitHub Release with bilingual notes and sequential `ARETE-###` code.
- Keep local/hosted model calls out of tests and benchmarks.

## Proposed architecture

- Add a minimal Electron shell and use electron-builder for Windows NSIS, Linux `.deb`, and AppImage output.
- Bundle the FastAPI app as a PyInstaller onedir sidecar. Build Windows and Linux binaries on their corresponding native runners; do not cross-compile the Python sidecar.
- Electron chooses a free loopback port, starts the sidecar with `HAMARTIA_HOST=127.0.0.1`, `HAMARTIA_PORT`, and `HAMARTIA_DATA_DIR=<userData>/data`, waits for `/healthcheck/ready`, and opens the app in a context-isolated BrowserWindow with Node integration disabled.
- Serve `frontend/dist` from the FastAPI process in packaged mode so the UI and API share one local HTTP origin. Keep Vite and the existing `scripts/dev.py` flow for source development.
- Preserve the existing JSON data and backup formats. Add a migration/preservation test for the per-user data-directory change.

Use [electron-builder's multi-platform build guidance](https://www.electron.build/v26/docs/features/multi-platform-build/) and [PyInstaller's operating-mode guidance](https://pyinstaller.org/en/stable/operating-mode.html): build each native backend on its target OS and validate the onedir bundle before distributing it.

## Release workflow

- Trigger a release only after a pull request has merged.
- Build Windows and Linux artifacts on native runners, collect them after all builds pass, then create one release.
- Serialize release jobs and calculate the next code from existing `ARETE-###` tags to avoid duplicates.
- Keep the bilingual release notes in `RELEASES.md`; include installation, data location, and limitations.
- The initial release workflow cannot publish installable artifacts for PRs merged before it exists. Decide whether to backfill the first release after packaging is verified.

## Main risks and gates

- Electron packages embed Chromium and increase download size; measure actual artifacts before selecting release limits.
- AppImage and `.deb` need native Linux integration checks; Windows installer needs a Windows runner.
- Secrets and user records must stay outside the renderer, installer directory, logs, and release assets.
- Test built static serving with SPA fallback and all API routes before enabling package builds.
- Do not claim a platform works until its native install/launch/persistence smoke passes.
