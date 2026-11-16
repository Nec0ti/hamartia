# 2026-11-16 backup restore crash recovery

## Change

Restore now extracts and validates to a unique sibling staging directory, preserves the existing local API key there, syncs the staged tree, and atomically publishes a sibling journal before changing the live directory. The journal identifies the staged directory and the optional `.before-restore-*` snapshot. The live-to-snapshot and staged-to-live renames are followed by parent-directory syncs; the journal is removed only after the new directory is installed.

On Windows, journal publication and same-volume journal/data-directory moves use `MoveFileExW` with `MOVEFILE_WRITE_THROUGH`; failures stop the restore and enter the existing rollback/recovery path. POSIX continues to use `os.replace`/`Path.rename` and parent-directory `fsync`.

App startup recovers the journal before `secure_data_tree` can create `DATA_DIR`. `StorageService` also recovers before its constructor creates the directory, covering early/direct storage callers. Recovery finishes a journaled restore and retains the old snapshot; an ordinary caught exception rolls back to the old directory and removes the staged tree. The ZIP format, exported-key omission, restore-time local-key preservation, and empty-destination behavior are unchanged.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_backup.py -q` — 27 passed; 1 Windows-only test skipped on Linux. Existing fault injection simulates process death after journal publication, after each directory rename, after journal removal, and before journal publication; a fresh startup or storage initialization recovers the state. Missing and empty destinations are covered.
- Windows CI runs `backend/tests/test_backup.py`; its child-process test exits with `os._exit` before/after journal publication, after each data-directory rename, and after journal removal, then checks recovery in a fresh process. These are process-termination checks, not power-cut tests. CI result: pending PR run.
- `python -m compileall -q backend/app/services/backup.py backend/app/services/storage.py backend/app/main.py backend/tests/test_backup.py` — passed.
- `git diff --check` — clean.
- No AI/provider or server was run.

## Durability and limits

On POSIX, restore fsyncs staged and existing data files, directories, the journal, and the parent after each rename or journal removal. The rename sequence is same-filesystem because stage, journal, and snapshot are siblings of `DATA_DIR`. This relies on filesystem support for atomic same-filesystem rename and directory fsync; storage devices or filesystems that ignore flushes can weaken power-loss guarantees.

Windows still flushes staged and existing file contents with `os.fsync`; the rename helper requests `MOVEFILE_WRITE_THROUGH` for journal publication and same-volume moves. Microsoft documents that the call does not return until an item is moved on disk and provides a directory-move example using this flag ([`MoveFileExW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw), [moving directories](https://learn.microsoft.com/en-us/windows/win32/fileio/moving-directories)). The explicit flush guarantee in the API reference is for copy/delete moves; these sibling operations are same-volume. Windows has no portable Python directory `fsync`, and the cited API documentation does not establish complete power-loss durability for every filesystem, storage controller, or volatile device cache. The exact guarantee is therefore: file contents are flushed and journal publication and same-volume moves request Win32 write-through; recovery is tested after process termination. Full Windows power-loss durability is not claimed.

Open hardware limit: no physical Windows 10/11 power-cut test has been run. Filesystem and storage hardware must honor flush requests for stronger persistence; Windows CI and `os._exit` tests cannot validate that behavior. Keep hardware-level durability as an open verification item in `backlog.md`.
