# Local OpenAI-compatible server option clarity

## Scope

The optional second Study Agent provider is now labeled **Local OpenAI-compatible server (optional)** in English and **Yerel OpenAI uyumlu sunucu (isteğe bağlı)** in Turkish. The Study Agent page explains that this option is commonly used with a server on the same computer, while its configured URL may still point to a remote host. Settings names the URL as local or remote. When this provider is selected, a short EN/TR note repeats the remote-endpoint caveat and links to setup guidance.

Existing per-request consent, exact-destination review, non-loopback host, unencrypted HTTP, operator-retention, and API-key warnings remain in place. English remains the first-run language; the existing language tests verify that default. No provider, model, or inference call was made.

The bilingual Study Agent wiki includes these examples:

- Ollama: `ollama pull qwen3:8b`, URL `http://localhost:11434/v1/`, model `qwen3:8b`; a blank client key is acceptable because Ollama documents ignoring it.
- LM Studio: start the Developer server or run `lms server start`, use `http://localhost:1234/v1`, and copy the model ID from `curl http://localhost:1234/v1/models`. The API key may be blank unless server authentication is enabled.
- Both examples identify the port and model as defaults/examples that may vary. The page warns that configuring a remote server requires a reachable address and that a model name or OpenAI-compatible API does not prove where inference runs or who can access it.

Official documentation consulted on 2026-11-15:

- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) and [Ollama Qwen3 model catalog](https://ollama.com/library/qwen3).
- [LM Studio OpenAI compatibility](https://lmstudio.ai/docs/developer/openai-compat), [LM Studio model IDs](https://lmstudio.ai/docs/developer/openai-compat/models), and [LM Studio server start and bind options](https://lmstudio.ai/docs/cli/serve/server-start). LM Studio documents the loopback default and warns that binding beyond localhost exposes the server outside the computer.

The docs catalog in `scripts/build_docs.py` is the source for the generated English and Turkish pages. It also restores the already-shipped learning-evidence reflection and backup descriptions that had been present in generated pages but omitted from the generator; regeneration therefore no longer drops that existing bilingual documentation.

## Verification

- `npm ci` — installed the lockfile dependency set; npm reported 0 vulnerabilities.
- `npm test` — passed, 27 tests. This includes bilingual label and remote-endpoint copy assertions; existing language tests retain English as the default.
- `npm run build` — passed. Vite reported the existing large-chunk advisory (the main JavaScript bundle is about 803 kB before gzip).
- `python3 -m py_compile scripts/build_docs.py` — passed.
- `python3 scripts/build_docs.py` — regenerated the bilingual wiki from the catalog.
- `python3 scripts/benchmark_docs.py` — passed offline integrity checks: 17 pages per locale, 34 navigation routes, 816 internal links/assets, 17 paired section-anchor orders, and 106 exact evidence excerpts. Final rendered-wiki SHA-256: `c2f381597e59c4b718499a72b0744cae00e1c2dc931e7b8c0bdeb0e5926a5500`.
- `nix shell nixpkgs#chromium --command sh -c 'PLAYWRIGHT_CHROMIUM_EXECUTABLE=$(command -v chromium) npm --prefix frontend run test:docs'` — passed in Chromium. The static docs smoke visited 34 pages and checked reciprocal locale links, section parity, internal links, 390px layout, keyboard skip link, and the new official setup links/copy.
- `git diff --check` — passed.

## Limits

The browser smoke covers the static documentation, not an interactive desktop-app provider selection or an actual Ollama/LM Studio connection. External provider links were consulted as official source material, but the offline checker does not fetch links. Human bilingual retrieval runs and fixed-viewport screenshot review remain pending. No AI/provider/model test or benchmark was run.
