# GitHub Pages URL diagnosis and AI handoff guide

## Pages diagnosis

The Pages API for `Nec0ti/hamartia` reports the public URL as `https://nec0ti.github.io/hamartia/`, with workflow-based publishing from `master`, HTTPS enforced, and the repository public. The `0` in `nec0ti` is the digit zero. The live project URLs using that spelling both returned HTTP 200 for HEAD and GET:

- `https://nec0ti.github.io/hamartia/`
- `https://nec0ti.github.io/hamartia/tr/`

The same paths on `https://necoti.github.io/` (letter `o`) returned HTTP 404 for both methods. The hostname typo explains the reported 404; the deployment was not missing or under a different base path.

Pages workflow run [43695431106](https://github.com/Nec0ti/hamartia/actions/runs/43695431106) completed successfully from master SHA `c3d99c4aa9bcc8b9bbbc4dd883063410be7a1806`. Its environment URL was `https://nec0ti.github.io/hamartia/`. The Pages API confirmed `build_type: workflow`, `source.branch: master`, `source.path: /`, and `https_enforced: true`.

The run's `github-pages` artifact (artifact ID `14153423606`) contained `index.html`, `tr/index.html`, and `styles.css` at the archive root. That matches the workflow's `path: docs`. The English page refers to `styles.css` and `tr/` relative to its project URL; the Turkish page refers to `../styles.css` and `../`. Both resolve correctly beneath the `/hamartia/` project base. There is no Vite build or `base href` involved in publishing these static HTML files.

No Pages workflow or configuration fix was needed. The public pages now declare canonical URLs containing the zero, and the EN/TR language switch continues to use paths relative to the project base.

## Public guide changes

The English and Turkish guides now describe Hamartia as a local-first tool for finding patterns in mistakes and turning them into targeted practice and review. They explain its Turkish mock-exam origins and current limits: exam types are TYT, AYT, or single-subject; subject/topic labels are free text; the built-in net calculation uses the YKS wrong-answer penalty; and the interface is currently English/Turkish. They state that different exam structures or scoring rules may need a contribution or fork and link the MIT license. The guides also describe Maarif-aligned AI as a future design direction, not a shipped capability: the current Study Agent does not map to Maarif learning outcomes or assess the full learning process.

The guides also include practical manual handoff steps for the configured OpenAI-compatible Study Agent provider and packaged desktop ChatGPT provider. The steps use fictional prompts, ask the user to review the destination and per-request consent, warn that a configured endpoint may be remote and its operator may retain requests, cover endpoint error and no-fallback behavior, and describe checking ChatGPT sign-out/revocation. Optional question analysis uses a disposable invented text question and synthetic image and notes that this flow can send question text or an image to the configured endpoint. The guide tells users to keep keys, tokens, and real study details out of reports and screenshots.

No account credentials, API keys, tokens, or real study content were used or recorded. No local endpoint, ChatGPT account, or model was called. The manual P3 endpoint and P5 ChatGPT checks remain for the user's own computer.

## Verification

- GitHub Pages API configuration and the successful workflow run/artifact were inspected.
- HEAD and GET against both canonical EN/TR URLs returned HTTP 200. HEAD and GET against the letter-`o` typo returned HTTP 404.
- The deployed archive was inspected and its root file layout matched the workflow upload path.
- `npm ci --ignore-scripts` — existing frontend lockfile installed; no lifecycle scripts ran.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/nix/store/r0f9i35n3r7rng8162xih4c1dag0s1vw-chromium-156.0.8078.47/bin/chromium npm run test:docs` — passed for English and Turkish canonical links, manual guide headings, YKS scoring qualification, MIT license link, language navigation, mobile layout, and no external requests.
- `git diff --check` — passed.

The browser check serves the public guide locally. After a future merge, verify both live canonical URLs again; PR CI does not publish Pages.
