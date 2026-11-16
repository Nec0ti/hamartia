# POSIX local data permissions

Date: 2026-11-16
Scope: owner-only POSIX permissions for Hamartia's local app data, stored API key and student profile, uploaded images, backup archives, and restore staging/final data. Windows permission and ACL handling is unchanged. This does not add encryption.

## Changes

- App startup applies mode `0700` to the existing data directory tree and `0600` to existing regular files without following symlinks. Newly created data directories are explicitly restricted.
- Atomic JSON temporary files and uploaded images are created as `0600`; atomic replacement keeps that mode on saved data.
- Backup snapshots and extracted restore files/directories use `0600`/`0700`. Restore also restricts the retained pre-restore snapshot, and backup ZIP outputs are created as `0600` on POSIX.
- POSIX mode handling is gated by `os.name == "posix"`; no Windows ACL changes or encryption behavior were added.

## Verification

- Focused storage, upload, backup, and restore permission assertions passed with umask `022` and permissive existing files/directories.
- `PYTHONPATH=backend python -m unittest discover -s backend/tests -v`: 299 tests passed; 9 PostgreSQL integration tests skipped because no test database URL was configured.
- `PYTHONPATH=backend python backend/benchmarks/benchmark_storage.py`: passed 1,000-record append/read/update/delete and progression checks; sequential JSON append is explicitly a stress case.
- `PYTHONPATH=backend python backend/benchmarks/benchmark_questions.py`: passed persisted upload/review/edit/delete correctness checks.
- `PYTHONPATH=backend python backend/benchmarks/benchmark_backup.py`: passed export, validation, restore, corruption, and path traversal checks.
- Benchmarks used synthetic local data, reported `ai_included: false`, and made no provider or local-model calls.

## Limits

Linux POSIX mode behavior was exercised. Windows ACL preservation was maintained by skipping chmod calls but was not tested on a Windows runner in this change. Owner-only filesystem modes do not encrypt data and cannot protect against other processes running as the same user or a compromised account.
