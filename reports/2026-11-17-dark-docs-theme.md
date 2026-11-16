# Dark documentation theme and README mark

## Scope

Changed the shared static docs template and CSS to use stacked dark header bars, current desktop package version context, a distinct User Manual tab, grouped documentation navigation, a persistent desktop sidebar, right-side section links, charcoal surfaces, blue links/active states, and responsive mobile navigation. The 17 English and 17 Turkish page bodies and section IDs remain unchanged. The README now has a compact icon beside its H1, with a white mark selected in dark mode and the existing high-contrast tile favicon as the default image.

## Verification

- `python3 -m py_compile scripts/build_docs.py` — passed.
- `python3 scripts/build_docs.py` — generated all 34 EN/TR pages.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) NODE_PATH=/home/necoti/hamartia-clock/frontend/node_modules npm --prefix frontend run test:docs'` — passed all 34 routes, reciprocal language links, section parity, internal links, 390 px overflow, and keyboard skip link.
- `python3 scripts/benchmark_docs.py --output /tmp/hamartia-docs-theme-benchmark.json` — passed offline integrity checks: 17 routes per locale, 34 active nav items, 1,060 local links/assets, 156 exact evidence excerpts, and zero errors. No network or AI was used.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) node /tmp/hamartia-docs-theme-preview.cjs'` — captured and visually inspected full-page 1440 px and 390 px docs screenshots, plus the README mark in Chromium with both light and dark color schemes. The preview server served the repo root so the relative asset paths match the README.
- `gh api /markdown --input /tmp/hamartia-readme-markdown.json` — GitHub's GFM renderer retained the `<picture>`, dark-mode `<source>`, and visible fallback `<img>` in the README title.
- `git diff --check` — passed.

## Limits

The README color-scheme preview used Chromium's `prefers-color-scheme` emulation and the repository's relative assets; it does not replace checking GitHub's rendered PR page after upload. The docs smoke is a route, layout, and basic keyboard check, not a complete WCAG or screen-reader audit. The integrity benchmark reports human retrieval pilot and screenshot-run fields as pending by design. No AI/model/provider execution or external-link fetching was performed.
