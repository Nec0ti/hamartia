import json
import tempfile
import unittest
import zipfile
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from app.models.schemas import CosmosData, Exam, PracticeSession, Question, ReviewAttempt, Settings, UserStats
from app.services.backup import BackupError, JSON_MODELS, create_backup, extract_backup, restore_backup
from app.services.data_lock import DataDirectoryBusy, DataDirectoryLock
from app.services.storage import StorageService
from desktop_server import restore_backup_command


def make_data(data_dir, exam_id, api_key):
    data_dir.mkdir(parents=True, exist_ok=True)
    storage = StorageService(data_dir)
    storage.save_list("exams.json", [Exam(
        id=exam_id, date="2026-11-14", subject="Matematik", correct=8, incorrect=2, blank=1,
    )])
    storage.save_list("questions.json", [Question(
        id="q1", image_name="q1.png", image_path="uploads/q1.png", ocr_text="x + 1",
    )])
    storage.save_doc("user.json", UserStats(total_xp=123))
    storage.save_doc("cosmos.json", CosmosData())
    storage.save_list("agent_documents.json", [{"id": "doc1.txt", "filename": "lesson.txt"}])
    storage.save_list("practice_sessions.json", [PracticeSession(
        id="practice1", date="2026-11-14", subject="Matematik", topic="Fonksiyon",
        correct=6, incorrect=2, blank=1,
    )])
    storage.save_doc("settings.json", Settings(
        litellm_base_url="http://local.test/v1", model_name="local-model", api_key=api_key,
    ))
    (data_dir / "uploads").mkdir(exist_ok=True)
    (data_dir / "uploads/q1.png").write_bytes(b"image bytes")
    (data_dir / "uploads/doc1.txt").write_bytes(b"study notes")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        make_data(self.source, "saved-exam", "must-not-be-exported")
        self.archive = self.root / "hamartia.zip"
        create_backup(self.source, self.archive)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_contains_all_data_and_omits_api_key(self):
        with zipfile.ZipFile(self.archive) as archive:
            self.assertTrue(set(JSON_MODELS).issubset(archive.namelist()))
            self.assertEqual(archive.read("uploads/q1.png"), b"image bytes")
            self.assertEqual(archive.read("uploads/doc1.txt"), b"study notes")
            self.assertEqual(json.loads(archive.read("practice_sessions.json"))[0]["id"], "practice1")
            self.assertEqual(json.loads(archive.read("settings.json"))["api_key"], "")
            self.assertNotIn(b"must-not-be-exported", archive.read("settings.json"))

    def test_restore_round_trip_keeps_local_key_and_snapshots_previous_data(self):
        target = self.root / "target"
        make_data(target, "current-exam", "current-local-key")

        result = restore_backup(self.archive, target)

        self.assertEqual([exam["id"] for exam in read_json(target / "exams.json")], ["saved-exam"])
        self.assertEqual(read_json(target / "settings.json")["api_key"], "current-local-key")
        self.assertEqual((target / "uploads/q1.png").read_bytes(), b"image bytes")
        self.assertEqual((target / "uploads/doc1.txt").read_bytes(), b"study notes")
        self.assertEqual(read_json(target / "practice_sessions.json")[0]["id"], "practice1")
        self.assertTrue(Path(result["snapshot"]).is_dir())
        self.assertEqual([exam["id"] for exam in read_json(Path(result["snapshot"]) / "exams.json")], ["current-exam"])

    def test_restore_to_empty_directory_uses_blank_api_key_and_has_no_snapshot(self):
        target = self.root / "new-device"

        result = restore_backup(self.archive, target)

        self.assertEqual(result["snapshot"], "")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "")
        self.assertEqual(read_json(target / "exams.json")[0]["id"], "saved-exam")

    def test_full_mock_sections_survive_backup_restore(self):
        mock = Exam(
            id="full-tyt", date="2026-11-14", exam_type="tyt", subject="TYT Geneli",
            correct=55, incorrect=13, blank=12,
            sections=[
                {"subject": "Türkçe", "correct": 30, "incorrect": 5, "blank": 5},
                {"subject": "Matematik", "correct": 25, "incorrect": 8, "blank": 7},
            ],
        )
        StorageService(self.source).save_list("exams.json", [mock])
        archive_path = self.root / "full-mock.zip"
        create_backup(self.source, archive_path)
        target = self.root / "full-mock-restored"

        restore_backup(archive_path, target)

        restored = StorageService(target).load_list("exams.json", Exam)
        self.assertEqual(len(restored), 1)
        self.assertEqual([section.subject for section in restored[0].sections], ["Türkçe", "Matematik"])
        self.assertEqual((restored[0].correct, restored[0].incorrect, restored[0].blank), (55, 13, 12))

    def test_review_attempt_calendar_day_survives_backup_restore(self):
        question = Question(
            id="q-local-day", review_attempts=[ReviewAttempt(
                attempted_at="2026-11-14T22:30:00Z", attempt_day="2026-11-15", correct=True,
            )],
        )
        StorageService(self.source).save_list("questions.json", [question])
        archive_path = self.root / "local-day.zip"
        create_backup(self.source, archive_path)
        target = self.root / "local-day-restored"

        restore_backup(archive_path, target)

        restored = StorageService(target).load_list("questions.json", Question)
        self.assertEqual(restored[0].review_attempts[0].attempt_day, "2026-11-15")

    def test_restore_accepts_legacy_backup_without_practice_sessions(self):
        legacy = self.root / "legacy.zip"
        with zipfile.ZipFile(self.archive) as source:
            files = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
            manifest = json.loads(source.read("manifest.json"))
        files.pop("practice_sessions.json")
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != "practice_sessions.json"]
        with zipfile.ZipFile(legacy, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, raw in files.items():
                target.writestr(name, raw)
            target.writestr("manifest.json", json.dumps(manifest))
        restored = self.root / "legacy-restored"

        restore_backup(legacy, restored)

        self.assertEqual(read_json(restored / "practice_sessions.json"), [])

    def test_restore_command_uses_selected_data_directory(self):
        target = self.root / "cli-data"
        environment = os.environ | {"HAMARTIA_DATA_DIR": str(target)}
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[2] / "scripts/restore_backup.py"), str(self.archive)],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(read_json(target / "exams.json")[0]["id"], "saved-exam")
        self.assertIn("Yedek geri yüklendi.", result.stdout)

    def test_desktop_restore_command_preserves_key_and_snapshot(self):
        target = self.root / "desktop-data"
        make_data(target, "current-exam", "current-local-key")

        code, status = restore_backup_command(self.archive, target)

        self.assertEqual(code, 0)
        self.assertEqual(status, "Backup restored successfully.")
        self.assertEqual(read_json(target / "exams.json")[0]["id"], "saved-exam")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "current-local-key")
        snapshots = list(self.root.glob("desktop-data.before-restore-*"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(read_json(snapshots[0] / "exams.json")[0]["id"], "current-exam")

    def test_desktop_restore_command_rejects_invalid_backup_without_changes(self):
        target = self.root / "desktop-invalid-data"
        make_data(target, "keep-me", "local-key")
        invalid = self.root / "invalid.zip"
        invalid.write_bytes(b"not a zip")

        code, status = restore_backup_command(invalid, target)

        self.assertNotEqual(code, 0)
        self.assertEqual(status, "Restore failed: the backup is invalid or could not be applied.")
        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")
        self.assertFalse(list(self.root.glob("desktop-invalid-data.before-restore-*")))

    def test_desktop_restore_command_rejects_active_data_lock(self):
        target = self.root / "desktop-locked-data"
        make_data(target, "keep-me", "local-key")

        with DataDirectoryLock(target):
            code, status = restore_backup_command(self.archive, target)

        self.assertEqual(code, 2)
        self.assertEqual(status, "Restore failed: the data directory is in use.")
        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")

    def test_export_materializes_defaults_when_data_files_are_missing(self):
        empty = self.root / "empty"
        empty.mkdir()
        archive_path = self.root / "empty.zip"
        create_backup(empty, archive_path)
        restored = self.root / "empty-restored"

        restore_backup(archive_path, restored)

        self.assertEqual(read_json(restored / "exams.json"), [])
        self.assertEqual(read_json(restored / "questions.json"), [])
        self.assertEqual(read_json(restored / "agent_documents.json"), [])
        self.assertEqual(read_json(restored / "settings.json")["api_key"], "")

    def test_invalid_schema_is_rejected_even_when_checksum_matches(self):
        invalid = self.root / "invalid-schema.zip"
        with zipfile.ZipFile(self.archive) as source:
            files = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
        files["questions.json"] = b"[{}]"
        manifest = json.loads(zipfile.ZipFile(self.archive).read("manifest.json"))
        for entry in manifest["files"]:
            if entry["path"] == "questions.json":
                entry["size"] = len(files["questions.json"])
                entry["sha256"] = hashlib.sha256(files["questions.json"]).hexdigest()
        with zipfile.ZipFile(invalid, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
            archive.writestr("manifest.json", json.dumps(manifest))
        target = self.root / "schema-target"
        make_data(target, "keep-me", "local-key")

        with self.assertRaises(BackupError):
            restore_backup(invalid, target)

        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")
        self.assertFalse(list(self.root.glob("schema-target.before-restore-*")))

    def test_invalid_checksum_does_not_change_existing_data(self):
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(self.archive) as source, zipfile.ZipFile(tampered, "w") as target:
            for name in source.namelist():
                raw = source.read(name)
                if name == "exams.json":
                    raw += b" "
                target.writestr(name, raw)
        data_dir = self.root / "untouched"
        make_data(data_dir, "keep-me", "local-key")
        before = {path.relative_to(data_dir).as_posix(): path.read_bytes() for path in data_dir.rglob("*") if path.is_file()}

        with self.assertRaises(BackupError):
            restore_backup(tampered, data_dir)

        after = {path.relative_to(data_dir).as_posix(): path.read_bytes() for path in data_dir.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        self.assertFalse(list(self.root.glob("untouched.before-restore-*")))

    def test_path_traversal_archive_is_rejected_without_writing_outside(self):
        malicious = self.root / "traversal.zip"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../escape.txt", b"bad")
        destination = self.root / "extract"

        with self.assertRaises(BackupError):
            extract_backup(malicious, destination)

        self.assertFalse((self.root / "escape.txt").exists())
        self.assertFalse(destination.exists())

    def test_symlink_upload_prevents_backup(self):
        outside = self.root / "outside.txt"
        outside.write_text("private", encoding="utf-8")
        link = self.source / "uploads/outside.txt"
        link.symlink_to(outside)

        with self.assertRaises(BackupError):
            create_backup(self.source, self.root / "symlink.zip")

    def test_symlink_upload_directory_prevents_backup(self):
        uploads = self.source / "uploads"
        original = self.source / "uploads-original"
        uploads.rename(original)
        uploads.symlink_to(original, target_is_directory=True)

        with self.assertRaises(BackupError):
            create_backup(self.source, self.root / "symlink-directory.zip")

    def test_restore_refuses_to_run_while_api_owns_data_directory(self):
        target = self.root / "locked"
        make_data(target, "keep-me", "local-key")

        with DataDirectoryLock(target):
            with self.assertRaises(DataDirectoryBusy):
                restore_backup(self.archive, target)

        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")

    def test_failed_directory_swap_rolls_back_previous_data(self):
        target = self.root / "rollback"
        make_data(target, "keep-me", "local-key")
        rename = Path.rename

        def fail_new_data(source, destination):
            if source.name == "data" and ".rollback.restore-" in str(source.parent):
                raise OSError("simulated staging rename failure")
            return rename(source, destination)

        with patch.object(Path, "rename", fail_new_data):
            with self.assertRaises(BackupError):
                restore_backup(self.archive, target)

        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")
        self.assertFalse(list(self.root.glob("rollback.before-restore-*")))


if __name__ == "__main__":
    unittest.main()
