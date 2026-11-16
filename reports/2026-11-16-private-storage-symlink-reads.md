# POSIX private-storage symlink read hardening

## Change

The shared data-tree hardener now fails closed on a symlinked data root, nested directory, or file. It reports the offending path and does not change or remove the link target. JSON storage opens existing records with `O_NOFOLLOW` where the platform provides it, so a link introduced after startup is rejected at read time. Backup and restore translate hardening failures to `BackupError`, preserving their existing error contract.

Focused coverage exercises linked settings, student onboarding, exam profiles, and exam records; linked data and uploads directories; backup snapshot creation; and restore. It checks that outside contents and POSIX modes remain unchanged. Existing question-upload tests also cover a linked uploads root.

## Verification

- Full backend suite: **296 passed, 9 skipped, 283 subtests passed**.
- Skips: the existing PostgreSQL integration tests, which require `HAMARTIA_SOCIAL_TEST_DATABASE_URL`.
- Warnings: existing Starlette/httpx and `datetime.utcnow()` deprecations.
- No benchmark was run: throughput measurements do not validate symlink isolation. No provider, local AI, server, or credential-backed path was invoked.
- `git diff --check` and Python bytecode compilation passed.

## Limits

The no-follow read guarantee depends on `O_NOFOLLOW`, available on the target POSIX systems; platforms without it receive a pre-open symlink check. Startup hardening rejects any symlink inside the data tree, so users who intentionally store application data through symlinked folders must move the data to a real directory or choose a direct data path. The checks cover the configured data directory and its contents; they do not validate every ancestor component above that configured path.
