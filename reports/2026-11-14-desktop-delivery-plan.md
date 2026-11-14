# Desktop packaging and release automation: implementation and verification

## Result

PR [#5](https://github.com/Nec0ti/hamartia/pull/5) merged on 2026-11-14 as `26ee65afc0d986ac170e7eb9f366f450327a5f36`. Native package jobs passed on Windows Server 2022 and Ubuntu 22.04. The merge automatically published [ARETE-001](https://github.com/Nec0ti/hamartia/releases/tag/ARETE-001) with all three installers and bilingual notes. GitHub Pages deployed successfully in [run #43639863699](https://github.com/Nec0ti/hamartia/actions/runs/43639863699); the live page at <https://nec0ti.github.io/hamartia/> returned the Hamartia title.

## Implemented delivery

- Electron starts a bundled PyInstaller FastAPI sidecar, binds it to an ephemeral loopback port, serves the bundled Vite UI on the same origin, and stores records under the current user's application data directory.
- The app uses an isolated renderer and validates that desktop-origin write requests are same-origin. Restore stops and waits for the sidecar before swapping the validated backup and restarts it afterward.
- Native builds produce a Windows NSIS installer, Debian `.deb`, and AppImage. GitHub Actions runs backend persistence, unpacked Electron UI, installed-app launch, and cleanup checks on native runners.
- A merged-PR workflow builds both platform packages, reserves the next `ARETE-###` release, checks and repairs missing release assets on retries, publishes bilingual notes, and appends those notes to `RELEASES.md`.
- `ARETE-001` is the first real release from this workflow. It was triggered by PR #5's merge; the release workflow list shows one publish run, with no duplicate release run caused by recording the ledger entry.

## CI and local verification

- GitHub Actions [desktop package run #43639428659](https://github.com/Nec0ti/hamartia/actions/runs/43639428659) passed both native jobs. Windows silently installed the NSIS package, launched the installed app, and uninstalled it. Ubuntu installed and removed the `.deb`, launched the installed app, and launched the AppImage with `APPIMAGE_EXTRACT_AND_RUN=1` under Xvfb. Both jobs also passed the unpacked Electron smoke and frozen-backend persistence smoke.
- GitHub Actions [standard checks #43639428627](https://github.com/Nec0ti/hamartia/actions/runs/43639428627) passed the backend suite, all five backend benchmarks, frontend tests/build, docs smoke, and browser smoke.
- Local final run: backend 93/93, frontend 16/16, desktop 10/10, and release metadata helpers 4/4. The packaged backend smoke passed static SPA fallback and data persistence after restart; startup was 2,190.8 ms (`ai_included: false`).
- Local Vite build took 26.98 sec and emitted a 728.78 KB minified JS bundle (207.45 KB gzip). It retains Vite's warning that a generated chunk exceeds 500 KB. The local Chromium docs smoke could not start because this NixOS host lacks `libglib-2.0.so.0`; the corresponding GitHub-hosted browser jobs passed.
- No model calls or AI measurements were included.

## AI-free benchmark measurements

Local measurements on this host; results can vary with machine load.

| Benchmark | Workload and result |
| --- | --- |
| JSON exam storage | 1,000 appends: 18.5751 sec (53.84/sec); read 0.0129 sec; one update 0.0291 sec; one delete 0.0367 sec |
| Question workflow | 100 image uploads: 0.6818 sec (146.66/sec); listing 0.0008 sec; insights 0.0016 sec; review 0.0077 sec; text capture 0.9676 sec (103.35/sec) |
| Backup and restore | 50 x 2 MiB uploads (100 MiB): export 4.2818 sec; validation 0.676 sec; restore 0.659 sec; archive 104,900,287 bytes |
| Question-order summary | 1,000 records 0.011343 sec; 10,000 records 0.104692 sec |
| Topic-practice sessions | 1,000 sessions: summary 0.013591 sec, write 0.019222 sec, read 0.042513 sec; 10,000 sessions: 0.052153 / 0.124785 / 0.305127 sec |

## ARETE-001 artifacts

| Asset | Size | Download |
| --- | ---: | --- |
| Windows installer | 138,224,352 bytes | [Hamartia-win-x64.exe](https://github.com/Nec0ti/hamartia/releases/download/ARETE-001/Hamartia-win-x64.exe) |
| Debian package | 132,542,556 bytes | [Hamartia-linux-amd64.deb](https://github.com/Nec0ti/hamartia/releases/download/ARETE-001/Hamartia-linux-amd64.deb) |
| AppImage | 164,616,159 bytes | [Hamartia-linux-x86_64.AppImage](https://github.com/Nec0ti/hamartia/releases/download/ARETE-001/Hamartia-linux-x86_64.AppImage) |

The release description has both English and Turkish sections. `RELEASES.md` on `master` contains the same bilingual ARETE-001 record.

## Limits and follow-up

- Installer integration was verified on Windows Server 2022 and Ubuntu 22.04 runners, not through an interactive install on a consumer Windows 10/11 computer or a separate Debian machine. A clean-user upgrade/uninstall cycle and signed Windows installer are not verified.
- The AppImage smoke ran on Ubuntu 22.04 with Xvfb and extract-and-run enabled; graphical desktop integration and FUSE-based launching on other distributions remain unverified.
- Linux builder logs report the default Electron icon and unset `desktopName`; the app runs, but branding/window association can be improved.
- `npm audit` previously reported six moderate advisories in Electron Builder's development dependency tree. Production desktop dependencies reported no findings.
- The signed-in ChatGPT study agent and a real local model remain separate follow-up work. Neither was called in CI or benchmarks.
- The first release is published. Future merged PRs follow the same automation, but subsequent ARETE allocation has not yet been exercised with a second merge.
