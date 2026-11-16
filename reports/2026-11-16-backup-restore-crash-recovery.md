# 2026-11-16 backup restore crash recovery

## Change

Restore now extracts and validates to a unique sibling staging directory, preserves the existing local API key there, syncs the staged tree, and atomically publishes a sibling journal before changing the live directory. The journal identifies the staged directory and the optional `.before-restore-*` snapshot. The live-to-snapshot and staged-to-live renames are followed by parent-directory syncs; the journal is removed only after the new directory is installed.

App startup recovers the journal before `secure_data_tree` can create `DATA_DIR`. `StorageService` also recovers before its constructor creates the directory, covering early/direct storage callers. Recovery finishes a journaled restore and retains the old snapshot; an ordinary caught exception rolls back to the old directory and removes the staged tree. The ZIP format, exported-key omission, restore-time local-key preservation, and empty-destination behavior are unchanged.

## Verification

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_backup.py -q` — 27 tests passed. Fault injection simulates process death after journal publication, after each directory rename, after journal removal, and before journal publication; a fresh startup or storage initialization recovers the state. Missing and empty destinations are covered.
- `python -m compileall -q backend/app/services/backup.py backend/app/services/storage.py backend/app/main.py backend/tests/test_backup.py` — passed.
- `git diff --check` — clean.
- No AI/provider or server was run.

## Durability and limits

On POSIX, restore fsyncs staged and existing data files, directories, the journal, and the parent after each rename or journal removal. The rename sequence is same-filesystem because stage, journal, and snapshot are siblings of `DATA_DIR`. This relies on filesystem support for atomic same-filesystem rename and directory fsync; storage devices or filesystems that ignore flushes can weaken power-loss guarantees.

Windows uses the same-volume rename sequence and flushes file contents with `os.fsync`, but Python does not expose portable directory fsync there. Process termination is covered by the recovery journal; power-loss ordering of Windows directory metadata is not claimed as fully durable. Windows execution was not available in this focused validation.
