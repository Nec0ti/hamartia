import json
import asyncio
import io
import tempfile
import unittest
import zipfile
import hashlib
import os
import subprocess
import sys
import threading
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api import questions as question_api
from app.models.schemas import (
    ActiveClockTimer, ClockAlarm, ClockState, CosmosData, Exam, LearningEvidence, PracticeSession,
    LearningEvidenceDeletedApprovalLedger, PracticeDraft, Question, QuestionDeletedApprovalLedger, ReviewAttempt, Settings, UserStats,
)
from app.services.backup import (
    BackupError, JSON_MODELS, _freeze_clock_state_for_backup, _write_restore_journal,
    _prepare_clock_state_for_restore, create_backup, extract_backup, recover_restore, restore_backup,
)
from app.services.data_lock import DataDirectoryBusy, DataDirectoryLock
from app.services.storage import StorageService, data_mutation_lock
from app import main
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

    def test_learning_evidence_round_trips_and_legacy_backup_defaults_empty(self):
        evidence = LearningEvidence(
            id="learning_evidence_1", created_at="2026-11-15T10:00:00Z", date="2026-11-14",
            subject="Math", topic="Quadratics", activity="Solved fresh examples",
            observation="I corrected the sign error.", reference_url="https://example.org/work",
        )
        StorageService(self.source).save_list("learning_evidence.json", [evidence])
        approval_id = UUID("b7f3e7f0-e48f-4e75-9fe6-a0fcd82f38ee")
        StorageService(self.source).save_doc("learning_evidence_agent_approvals.json", LearningEvidenceDeletedApprovalLedger(approval_ids=[approval_id]))
        create_backup(self.source, self.archive)
        restored = self.root / "evidence-restored"
        restore_backup(self.archive, restored)
        self.assertEqual(StorageService(restored).load_list("learning_evidence.json", LearningEvidence), [evidence])
        self.assertEqual(
            StorageService(restored).load_doc("learning_evidence_agent_approvals.json", LearningEvidenceDeletedApprovalLedger),
            LearningEvidenceDeletedApprovalLedger(approval_ids=[approval_id]),
        )

        legacy = self.root / "legacy-evidence.zip"
        with zipfile.ZipFile(self.archive) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
            manifest = json.loads(archive.read("manifest.json"))
        files.pop("learning_evidence.json")
        files.pop("learning_evidence_agent_approvals.json")
        manifest["files"] = [item for item in manifest["files"] if item["path"] != "learning_evidence.json"]
        manifest["files"] = [item for item in manifest["files"] if item["path"] != "learning_evidence_agent_approvals.json"]
        with zipfile.ZipFile(legacy, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
            archive.writestr("manifest.json", json.dumps(manifest))
        legacy_restored = self.root / "legacy-evidence-restored"
        restore_backup(legacy, legacy_restored)
        self.assertEqual(StorageService(legacy_restored).load_list("learning_evidence.json", LearningEvidence), [])
        self.assertEqual(
            StorageService(legacy_restored).load_doc("learning_evidence_agent_approvals.json", LearningEvidenceDeletedApprovalLedger),
            LearningEvidenceDeletedApprovalLedger(),
        )

    def test_question_agent_deleted_approval_ledger_round_trips_and_defaults_for_legacy_backup(self):
        approval_id = UUID("09a75ba4-8912-4ff0-aab2-6a77c2bfe214")
        StorageService(self.source).save_doc(
            "question_agent_approvals.json", QuestionDeletedApprovalLedger(approval_ids=[approval_id]),
        )
        create_backup(self.source, self.archive)
        restored = self.root / "question-agent-restored"
        restore_backup(self.archive, restored)
        self.assertEqual(
            StorageService(restored).load_doc("question_agent_approvals.json", QuestionDeletedApprovalLedger),
            QuestionDeletedApprovalLedger(approval_ids=[approval_id]),
        )

        legacy = self.root / "legacy-question-agent.zip"
        with zipfile.ZipFile(self.archive) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
            manifest = json.loads(archive.read("manifest.json"))
        files.pop("question_agent_approvals.json")
        manifest["files"] = [item for item in manifest["files"] if item["path"] != "question_agent_approvals.json"]
        with zipfile.ZipFile(legacy, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
            archive.writestr("manifest.json", json.dumps(manifest))
        legacy_restored = self.root / "legacy-question-agent-restored"
        restore_backup(legacy, legacy_restored)
        self.assertEqual(
            StorageService(legacy_restored).load_doc("question_agent_approvals.json", QuestionDeletedApprovalLedger),
            QuestionDeletedApprovalLedger(),
        )

    def test_backup_snapshot_freezes_running_timers_at_snapshot_time(self):
        state = ClockState(active_timer=ActiveClockTimer(
            kind="practice", status="running", elapsed_ms=4_000, started_at_ms=10_000,
            practice_draft=PracticeDraft(date="2026-11-15", subject="Math", topic="Algebra"),
        ))

        frozen = ClockState.model_validate_json(_freeze_clock_state_for_backup(state.model_dump(), 16_500))

        self.assertEqual(frozen.active_timer.status, "paused")
        self.assertEqual(frozen.active_timer.elapsed_ms, 10_500)
        self.assertIsNone(frozen.active_timer.started_at_ms)
        self.assertEqual(frozen.active_timer.practice_draft.topic, "Algebra")

    def test_backup_restore_disables_alarms_and_preserves_timer_remainder(self):
        state = ClockState(
            alarms=[ClockAlarm(
                id="alarm-1", label="Review", kind="once", one_off_at_ms=50_000,
                next_at_ms=50_000, enabled=True,
            )],
            active_timer=ActiveClockTimer(
                kind="countdown", status="running", duration_ms=20_000,
                remaining_ms=20_000, deadline_at_ms=30_000,
            ),
        )

        restored = _prepare_clock_state_for_restore(state.model_dump(), 17_000)

        self.assertFalse(restored.alarms[0].enabled)
        self.assertEqual(restored.active_timer.status, "paused")
        self.assertEqual(restored.active_timer.remaining_ms, 13_000)
        self.assertIsNone(restored.active_timer.deadline_at_ms)

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

        if os.name == "posix":
            for path in (target, target / "uploads", Path(result["snapshot"]), Path(result["snapshot"]) / "uploads"):
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            for path in (target / "settings.json", target / "onboarding.json", target / "uploads/q1.png",
                         Path(result["snapshot"]) / "settings.json"):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits only")
    def test_owner_only_modes_ignore_umask_and_restrict_existing_data(self):
        previous_umask = os.umask(0o022)
        try:
            data_dir = self.root / "loose-data"
            data_dir.mkdir(mode=0o755)
            uploads = data_dir / "uploads"
            uploads.mkdir(mode=0o755)
            (data_dir / "settings.json").write_text('{"api_key":"local-secret"}', encoding="utf-8")
            (data_dir / "onboarding.json").write_text('{"profile":{"nickname":"student"}}', encoding="utf-8")
            (uploads / "question.png").write_bytes(b"image")

            async def start_app():
                async with main.lifespan(main.app):
                    pass

            with patch.object(main, "DATA_DIR", data_dir):
                asyncio.run(start_app())
            storage = StorageService(data_dir)
            storage.save_doc("settings.json", Settings(api_key="local-secret"))
            destination = self.root / "private-backup.zip"
            create_backup(data_dir, destination)
            restored = self.root / "restored-data"
            restore_backup(destination, restored)

            for path in (data_dir, uploads, restored, restored / "uploads"):
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            for path in (data_dir / "settings.json", data_dir / "onboarding.json", uploads / "question.png",
                         destination, restored / "settings.json", restored / "onboarding.json",
                         restored / "uploads/question.png"):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        finally:
            os.umask(previous_umask)

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

    def test_restore_accepts_legacy_backup_without_optional_clock_documents(self):
        legacy = self.root / "legacy.zip"
        with zipfile.ZipFile(self.archive) as source:
            files = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
            manifest = json.loads(source.read("manifest.json"))
        files.pop("practice_sessions.json")
        files.pop("clock.json")
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != "practice_sessions.json"]
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != "clock.json"]
        with zipfile.ZipFile(legacy, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, raw in files.items():
                target.writestr(name, raw)
            target.writestr("manifest.json", json.dumps(manifest))
        restored = self.root / "legacy-restored"

        restore_backup(legacy, restored)

        self.assertEqual(read_json(restored / "practice_sessions.json"), [])
        self.assertEqual(read_json(restored / "clock.json"), ClockState().model_dump(mode="json"))

    def test_restore_command_uses_selected_data_directory(self):
        target = self.root / "cli-data"
        environment = os.environ | {"HAMARTIA_DATA_DIR": str(target)}
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[2] / "scripts/restore_backup.py"), str(self.archive)],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

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

    def test_export_is_a_point_in_time_snapshot_while_live_writes_wait(self):
        data_dir = self.root / "snapshot-race"
        make_data(data_dir, "old-exam", "local-key")
        destination = self.root / "snapshot-race.zip"
        snapshot_reading_questions = threading.Event()
        continue_snapshot = threading.Event()
        writer_started = threading.Event()
        mutation_reached_write = threading.Event()
        original_read_bytes = Path.read_bytes
        original_write_atomic = StorageService._write_atomic

        def pause_before_questions(path):
            if path == data_dir / "questions.json":
                snapshot_reading_questions.set()
                if not continue_snapshot.wait(5):
                    raise TimeoutError("snapshot test did not resume")
            return original_read_bytes(path)

        def observe_mutation(storage, filename, payload):
            if storage.data_dir.resolve() == data_dir.resolve() and filename == "exams.json":
                mutation_reached_write.set()
            return original_write_atomic(storage, filename, payload)

        def add_exam_and_linked_question():
            writer_started.set()
            storage = StorageService(data_dir)
            storage.append_list("exams.json", Exam(
                id="new-exam", date="2026-11-15", subject="Physics", correct=1, incorrect=0, blank=0,
            ), Exam)
            upload = UploadFile(
                filename="question.png", file=io.BytesIO(b"\x89PNG\r\n\x1a\nfixture"),
                headers=Headers({"content-type": "image/png"}),
            )
            with patch.object(question_api, "DATA_DIR", data_dir), patch.object(
                question_api, "UPLOAD_DIR", data_dir / "uploads",
            ):
                return asyncio.run(question_api.upload_question(
                    upload, "linked question", "Physics", "Optics", storage, exam_id="new-exam",
                ))

        with patch.object(Path, "read_bytes", pause_before_questions), patch.object(
            StorageService, "_write_atomic", observe_mutation,
        ), ThreadPoolExecutor(max_workers=2) as pool:
            backup_future = pool.submit(create_backup, data_dir, destination)
            self.assertTrue(snapshot_reading_questions.wait(5))
            lock = data_mutation_lock(data_dir)
            lock_acquired = lock.acquire(blocking=False)
            if lock_acquired:
                lock.release()
            self.assertFalse(lock_acquired, "backup did not hold the snapshot lock")

            writer_future = pool.submit(add_exam_and_linked_question)
            self.assertTrue(writer_started.wait(5))
            self.assertFalse(mutation_reached_write.wait(0.1), "a live mutation crossed the snapshot lock")
            continue_snapshot.set()
            backup_future.result(timeout=5)
            new_question = writer_future.result(timeout=5)

        with zipfile.ZipFile(destination) as archive:
            archived_exams = json.loads(archive.read("exams.json"))
            archived_questions = json.loads(archive.read("questions.json"))
            archived_paths = archive.namelist()
        self.assertNotIn("new-exam", [item["id"] for item in archived_exams])
        self.assertNotIn(new_question.id, [item["id"] for item in archived_questions])
        self.assertNotIn(f"uploads/{new_question.image_name}", archived_paths)
        live_exams = StorageService(data_dir).load_list("exams.json", Exam)
        live_questions = StorageService(data_dir).load_list("questions.json", Question)
        self.assertIn("new-exam", [item.id for item in live_exams])
        self.assertIn(new_question.id, [item.id for item in live_questions])

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
        from app.services import backup as backup_service
        move = backup_service._move_path

        def fail_new_data(source, destination, replace=False):
            if source.name.startswith(".rollback.restore-stage-"):
                raise OSError("simulated staging rename failure")
            return move(source, destination, replace)

        with patch("app.services.backup._move_path", fail_new_data):
            with self.assertRaises(BackupError):
                restore_backup(self.archive, target)

        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")
        self.assertFalse(list(self.root.glob("rollback.before-restore-*")))

    def test_restore_recovers_after_each_commit_boundary_before_storage_initializes(self):
        class SimulatedCrash(BaseException):
            pass

        for boundary in ("journal", "old_rename", "new_rename", "journal_remove"):
            with self.subTest(boundary=boundary):
                target = self.root / f"crash-{boundary}"
                make_data(target, "keep-me", "local-key")
                from app.services import backup as backup_service
                real_move = backup_service._move_path
                real_unlink = Path.unlink
                real_write_journal = _write_restore_journal

                def crash_after_journal(*args):
                    real_write_journal(*args)
                    if boundary == "journal":
                        raise SimulatedCrash()

                def crash_after_rename(source, destination, replace=False):
                    result = real_move(source, destination, replace)
                    if boundary == "old_rename" and source == target:
                        raise SimulatedCrash()
                    if boundary == "new_rename" and destination == target and source.name.startswith(f".{target.name}.restore-stage-"):
                        raise SimulatedCrash()
                    return result

                def crash_after_unlink(path, *args, **kwargs):
                    result = real_unlink(path, *args, **kwargs)
                    if boundary == "journal_remove" and path.name == f".{target.name}.restore-journal.json":
                        raise SimulatedCrash()
                    return result

                with patch("app.services.backup._write_restore_journal", crash_after_journal), \
                     patch("app.services.backup._move_path", crash_after_rename), \
                     patch.object(Path, "unlink", crash_after_unlink):
                    with self.assertRaises(SimulatedCrash):
                        restore_backup(self.archive, target)

                if boundary == "old_rename":
                    async def start_app():
                        async with main.lifespan(main.app):
                            pass

                    with patch.object(main, "DATA_DIR", target):
                        asyncio.run(start_app())
                else:
                    # StorageService is the early caller that used to recreate an empty DATA_DIR.
                    StorageService(target)
                expected = "saved-exam"
                self.assertEqual(read_json(target / "exams.json")[0]["id"], expected)
                self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")
                self.assertFalse((self.root / f".{target.name}.restore-journal.json").exists())

    def test_restore_recovery_handles_missing_and_empty_targets(self):
        class SimulatedCrash(BaseException):
            pass

        for initially_empty in (False, True):
            with self.subTest(initially_empty=initially_empty):
                target = self.root / ("empty-existing" if initially_empty else "missing-target")
                if initially_empty:
                    target.mkdir()
                real_write_journal = _write_restore_journal

                def crash_after_journal(*args):
                    real_write_journal(*args)
                    raise SimulatedCrash()

                with patch("app.services.backup._write_restore_journal", crash_after_journal):
                    with self.assertRaises(SimulatedCrash):
                        restore_backup(self.archive, target)

                recover_restore(target)
                self.assertEqual(read_json(target / "exams.json")[0]["id"], "saved-exam")
                self.assertEqual(read_json(target / "settings.json")["api_key"], "")

    def test_restore_crash_before_journal_replace_leaves_live_data_untouched(self):
        class SimulatedCrash(BaseException):
            pass

        target = self.root / "journal-publish-crash"
        make_data(target, "keep-me", "local-key")
        from app.services import backup as backup_service
        real_move = backup_service._move_path

        def crash_before_publish(source, destination, replace=False):
            if destination == self.root / f".{target.name}.restore-journal.json":
                raise SimulatedCrash()
            return real_move(source, destination, replace)

        with patch("app.services.backup._move_path", crash_before_publish):
            with self.assertRaises(SimulatedCrash):
                restore_backup(self.archive, target)

        StorageService(target)
        self.assertEqual(read_json(target / "exams.json")[0]["id"], "keep-me")
        self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")

    @unittest.skipUnless(os.name == "nt", "Windows child-process termination coverage")
    def test_windows_child_termination_recovers_at_each_journal_and_rename_boundary(self):
        boundaries = ("journal_before", "journal", "old_rename", "new_rename", "journal_remove")
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                target = self.root / f"windows-crash-{boundary}"
                make_data(target, "keep-me", "local-key")
                script = "\n".join((
                    "import os",
                    "from pathlib import Path",
                    "from unittest.mock import patch",
                    "from app.services import backup",
                    f"target = Path({str(target)!r})",
                    f"boundary = {boundary!r}",
                    "move = backup._move_path",
                    "unlink = Path.unlink",
                    "write_journal = backup._write_restore_journal",
                    "def interrupted_move(source, destination, replace=False):",
                    "    if boundary == 'journal_before' and destination == backup._restore_journal_path(target):",
                    "        os._exit(73)",
                    "    result = move(source, destination, replace)",
                    "    if boundary == 'old_rename' and source == target:",
                    "        os._exit(73)",
                    "    if boundary == 'new_rename' and destination == target and source.name.startswith(f'.{target.name}.restore-stage-'):",
                    "        os._exit(73)",
                    "    return result",
                    "def interrupted_write(*args):",
                    "    result = write_journal(*args)",
                    "    if boundary == 'journal':",
                    "        os._exit(73)",
                    "    return result",
                    "def interrupted_unlink(path, *args, **kwargs):",
                    "    result = unlink(path, *args, **kwargs)",
                    "    if boundary == 'journal_remove' and path.name == f'.{target.name}.restore-journal.json':",
                    "        os._exit(73)",
                    "    return result",
                    "with patch('app.services.backup._move_path', interrupted_move), patch('app.services.backup._write_restore_journal', interrupted_write), patch.object(Path, 'unlink', interrupted_unlink):",
                    f"    backup.restore_backup({str(self.archive)!r}, target)",
                ))
                env = os.environ.copy()
                backend_root = str(Path(__file__).resolve().parents[1])
                env["PYTHONPATH"] = backend_root + os.pathsep + env.get("PYTHONPATH", "")
                child = subprocess.run([sys.executable, "-c", script], env=env, timeout=60)
                self.assertEqual(child.returncode, 73)

                recover_restore(target)
                expected = "keep-me" if boundary == "journal_before" else "saved-exam"
                self.assertEqual(read_json(target / "exams.json")[0]["id"], expected)
                self.assertEqual(read_json(target / "settings.json")["api_key"], "local-key")


if __name__ == "__main__":
    unittest.main()
