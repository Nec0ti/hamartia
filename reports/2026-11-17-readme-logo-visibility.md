# README logo visibility

## Scope

Reduced the inline README mark from 28 px to 20 px and switched its light-mode image from the tile favicon to the existing transparent black mark. Dark mode continues to use the existing transparent white mark.

## Verification

- `gh api /markdown --input /tmp/hamartia-readme-logo.json` — GitHub's GFM renderer retained the `<picture>` and its dark-mode source.
- Chromium with `prefers-color-scheme` set to light and dark — loaded the expected SVG variant in each theme; both screenshots were visually inspected and there were zero failed requests.
- `git diff --check` — passed.

No application tests were run; this change only affects the README image markup.
