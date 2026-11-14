# Settings API key redaction plan

## Problem

`GET /settings` and `PATCH /settings` return the full `Settings` model. Its `api_key` field is also copied into React state. Although the application's documented launcher is limited to loopback, processes on the same machine and allowed browser origins can read the key.

## Smallest safe change

- Never return the `api_key` value in API responses; return only whether a key is set.
- In PATCH, an empty/omitted key preserves the existing key; an explicit `clear_api_key` flag clears it. A newly entered key replaces the existing key.
- State in the Settings modal that a blank field preserves the key, and provide an explicit control to clear the saved key.
- Do not change the storage format or backup compatibility.

## Affected contract and scope

- Callers: `frontend/src/App.jsx`, `frontend/src/components/SettingsModal.jsx`, `frontend/src/services/api.js`, and the backend `/settings` route.
- Tests: new settings API tests cover GET/PATCH response redaction, preservation with an empty value, replacement with a new value, and explicit clearing.
- AI service, model calls, and benchmark flow remain unchanged. All checks use fake settings.

## Acceptance criteria

- No `/settings` response contains the secret key.
- Existing client fields can be edited and saved normally after GET.
- Saving without entering a key does not lose the existing key; a new key can be entered; the user can explicitly clear it.
- Backend tests, frontend test/build, and existing AI-free browser smoke pass.
- Measurement: no benchmark result will be added because the AI-free path is unchanged; report end-to-end settings and API checks.

## Sequence

1. Commit this plan and the backlog item.
2. Change settings response/update schema, form interaction, and API regression tests in one small code commit.
3. Run backend/frontend/browser checks, report the result, and create a separate docs commit.

## Known limit

This is not a secret vault against untrusted processes running with the same user permissions on the local machine. It removes unnecessary key exposure through HTTP/UI.
