import json
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import Exam, ExamScoringProfile, Settings, StudentOnboarding
from app.services.backup import BackupError, create_backup, restore_backup
from app.services.private_storage import secure_data_tree
from app.services.storage import StorageError, StorageService


class PrivateStorageSymlinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def symlink(self, target, link):
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable: {exc}")

    def test_storage_rejects_linked_settings_profile_and_record_json(self):
        targets = {
            "settings.json": json.dumps({"api_key": "attacker-controlled"}),
            "onboarding.json": json.dumps({"revision": 77}),
            "exam_profiles.json": "[]",
            "exams.json": json.dumps([{"id": "attacker-controlled", "date": "2026-11-16", "subject": "Math", "correct": 1, "incorrect": 0, "blank": 0}]),
        }
        storage = StorageService(self.data)
        for filename, contents in targets.items():
            with self.subTest(filename=filename):
                target = self.root / f"outside-{filename}"
                target.write_text(contents, encoding="utf-8")
                target.chmod(0o640)
                self.symlink(target, self.data / filename)
                with self.assertRaises(StorageError):
                    if filename == "settings.json":
                        storage.load_doc(filename, Settings)
                    elif filename == "onboarding.json":
                        storage.load_doc(filename, StudentOnboarding)
                    elif filename == "exam_profiles.json":
                        storage.load_list(filename, ExamScoringProfile)
                    else:
                        storage.load_list(filename, Exam)
                self.assertEqual(target.stat().st_mode & 0o777, 0o640)
                self.assertEqual(target.read_text(encoding="utf-8"), contents)
                (self.data / filename).unlink()

    def test_startup_hardening_rejects_linked_directory_without_touching_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        record = outside / "settings.json"
        record.write_text('{"api_key":"keep"}', encoding="utf-8")
        outside.chmod(0o750)
        self.symlink(outside, self.data / "uploads")

        with self.assertRaisesRegex(OSError, "symbolic-link data directory"):
            secure_data_tree(self.data)

        self.assertEqual(outside.stat().st_mode & 0o777, 0o750)
        self.assertEqual(record.read_text(encoding="utf-8"), '{"api_key":"keep"}')

    def test_data_directory_symlink_is_rejected_by_startup_and_restore(self):
        outside = self.root / "outside-data"
        outside.mkdir()
        record = outside / "settings.json"
        record.write_text('{"api_key":"keep"}', encoding="utf-8")
        outside.chmod(0o750)
        linked_data = self.root / "linked-data"
        self.symlink(outside, linked_data)

        with self.assertRaisesRegex(OSError, "symbolic-link directory"):
            StorageService(linked_data)
        with self.assertRaisesRegex(OSError, "symbolic-link data directory"):
            secure_data_tree(linked_data)

        archive = self.root / "backup.zip"
        create_backup(self.data, archive)
        with self.assertRaisesRegex(BackupError, "symbolic-link data directory"):
            restore_backup(archive, linked_data)

        self.assertEqual(outside.stat().st_mode & 0o777, 0o750)
        self.assertEqual(record.read_text(encoding="utf-8"), '{"api_key":"keep"}')

    def test_backup_and_restore_reject_linked_data_without_reading_or_replacing_target(self):
        archive = self.root / "backup.zip"
        safe_data = self.root / "safe-data"
        safe_data.mkdir()
        create_backup(safe_data, archive)

        outside = self.root / "outside-settings.json"
        outside.write_text('{"api_key":"keep"}', encoding="utf-8")
        outside.chmod(0o640)
        self.symlink(outside, self.data / "settings.json")

        with self.assertRaisesRegex(BackupError, "symbolic-link data file"):
            create_backup(self.data, self.root / "should-not-exist.zip")
        with self.assertRaisesRegex(BackupError, "symbolic-link data file"):
            restore_backup(archive, self.data)

        self.assertFalse((self.root / "should-not-exist.zip").exists())
        self.assertTrue((self.data / "settings.json").is_symlink())
        self.assertEqual(outside.stat().st_mode & 0o777, 0o640)
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"api_key":"keep"}')

    def test_backup_rejects_linked_upload_directory(self):
        outside = self.root / "outside-uploads"
        outside.mkdir()
        image = outside / "private.png"
        image.write_bytes(b"private")
        outside.chmod(0o750)
        self.symlink(outside, self.data / "uploads")

        with self.assertRaisesRegex(BackupError, "symbolic-link data directory"):
            create_backup(self.data, self.root / "should-not-exist.zip")

        self.assertEqual(outside.stat().st_mode & 0o777, 0o750)
        self.assertEqual(image.read_bytes(), b"private")


if __name__ == "__main__":
    unittest.main()
