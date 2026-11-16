"""Validated local ZIP export and offline restore for Hamartia data."""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from app.models.schemas import ClockState, CosmosData, Exam, ExamDeletedApprovalLedger, ExamScoringProfile, LearningEvidence, LearningEvidenceDeletedApprovalLedger, PracticeSession, Question, QuestionDeletedApprovalLedger, Settings, StudentOnboarding, UserStats
from app.services.data_lock import DataDirectoryLock
from app.services.private_storage import open_private_file, secure_data_tree, secure_directory
from app.services.storage import data_mutation_guard

BACKUP_FORMAT = "hamartia-local-backup"
BACKUP_VERSION = 1
JSON_MODELS = {
    "exams.json": ("list", Exam),
    "exam_agent_approvals.json": ("doc", ExamDeletedApprovalLedger),
    "sectioned_exam_agent_approvals.json": ("doc", ExamDeletedApprovalLedger),
    "exam_profiles.json": ("list", ExamScoringProfile),
    "questions.json": ("list", Question),
    "user.json": ("doc", UserStats),
    "cosmos.json": ("doc", CosmosData),
    "agent_documents.json": ("dict_list", dict),
    "settings.json": ("doc", Settings),
    "practice_sessions.json": ("list", PracticeSession),
    "learning_evidence.json": ("list", LearningEvidence),
    "learning_evidence_agent_approvals.json": ("doc", LearningEvidenceDeletedApprovalLedger),
    "question_agent_approvals.json": ("doc", QuestionDeletedApprovalLedger),
    "clock.json": ("doc", ClockState),
    "onboarding.json": ("doc", StudentOnboarding),
}
OPTIONAL_BACKUP_JSON = {"exam_profiles.json", "practice_sessions.json", "learning_evidence.json", "learning_evidence_agent_approvals.json", "question_agent_approvals.json", "exam_agent_approvals.json", "sectioned_exam_agent_approvals.json", "clock.json", "onboarding.json"}
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024
MAX_FILES = 10_000
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class BackupError(ValueError):
    """Raised when a backup cannot be created or restored safely."""


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _defaults():
    return {
        "exams.json": [],
        "exam_agent_approvals.json": ExamDeletedApprovalLedger().model_dump(mode="json"),
        "sectioned_exam_agent_approvals.json": ExamDeletedApprovalLedger().model_dump(mode="json"),
        "exam_profiles.json": [],
        "questions.json": [],
        "user.json": UserStats().model_dump(mode="json"),
        "cosmos.json": CosmosData().model_dump(mode="json"),
        "agent_documents.json": [],
        "settings.json": Settings().model_dump(mode="json"),
        "practice_sessions.json": [],
        "learning_evidence.json": [],
        "learning_evidence_agent_approvals.json": LearningEvidenceDeletedApprovalLedger().model_dump(mode="json"),
        "question_agent_approvals.json": QuestionDeletedApprovalLedger().model_dump(mode="json"),
        "clock.json": ClockState().model_dump(mode="json"),
        "onboarding.json": StudentOnboarding().model_dump(mode="json"),
    }


def _pause_clock_timer(timer, now_ms):
    if timer is None or timer.status != "running":
        return timer
    if timer.kind in ("countdown", "pomodoro"):
        deadline = timer.deadline_at_ms
        remaining = max(0, deadline - now_ms)
        if remaining == 0:
            return timer.model_copy(update={
                "status": "overdue", "deadline_at_ms": None, "started_at_ms": None,
                "remaining_ms": 0, "overdue_at_ms": deadline,
            })
        return timer.model_copy(update={
            "status": "paused", "deadline_at_ms": None, "started_at_ms": None,
            "remaining_ms": remaining, "overdue_at_ms": None,
        })
    elapsed = timer.elapsed_ms + max(0, now_ms - timer.started_at_ms)
    return timer.model_copy(update={
        "status": "paused", "started_at_ms": None, "deadline_at_ms": None,
        "elapsed_ms": elapsed, "overdue_at_ms": None,
    })


def _freeze_clock_state_for_backup(value, now_ms):
    state = ClockState.model_validate(value)
    timer = _pause_clock_timer(state.active_timer, now_ms)
    state = state.model_copy(update={"active_timer": timer})
    return _json_bytes(state.model_dump(mode="json"))


def _prepare_clock_state_for_restore(value, now_ms):
    state = ClockState.model_validate(value)
    timer = _pause_clock_timer(state.active_timer, now_ms)
    alarms = [alarm.model_copy(update={"enabled": False}) for alarm in state.alarms]
    return state.model_copy(update={"active_timer": timer, "alarms": alarms})


def _validate_json(name, raw):
    if len(raw) > MAX_JSON_BYTES:
        raise BackupError(f"JSON file is too large: {name}")
    try:
        value = json.loads(raw)
        kind, model = JSON_MODELS[name]
        if kind == "list":
            if not isinstance(value, list):
                raise ValueError("expected a JSON array")
            for item in value:
                model.model_validate(item)
        elif kind == "dict_list":
            if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
                raise ValueError("expected an array of objects")
        else:
            model.model_validate(value)
        return value
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise BackupError(f"Invalid {name}: {exc}") from exc


def _json_sources(data_dir):
    defaults = _defaults()
    result = {}
    for name in JSON_MODELS:
        source = Path(data_dir) / name
        if source.is_symlink():
            raise BackupError(f"Cannot back up a symbolic link: {name}")
        raw = source.read_bytes() if source.is_file() else _json_bytes(defaults[name])
        value = _validate_json(name, raw)
        if name == "settings.json":
            settings = Settings.model_validate(value)
            result[name] = _json_bytes(settings.model_dump(mode="json") | {"api_key": ""})
        else:
            result[name] = raw
    return result


def _safe_upload_path(value):
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        raise BackupError("Invalid upload reference in backup data")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or len(path.parts) < 2 or path.parts[0] != "uploads" or ".." in path.parts:
        raise BackupError("Invalid upload reference in backup data")
    return path.as_posix()


def _upload_references(json_files):
    questions = json.loads(json_files["questions.json"])
    docs = json.loads(json_files["agent_documents.json"])
    paths = set()
    for question in questions:
        if question.get("image_path"):
            paths.add(_safe_upload_path(question["image_path"]))
    for doc in docs:
        if doc.get("id"):
            paths.add(_safe_upload_path(f"uploads/{doc['id']}"))
    return paths


def _capture_backup_snapshot(data_dir, snapshot_dir):
    """Copy a stable, secret-filtered snapshot while writes are paused."""
    json_files = _json_sources(data_dir)
    snapshot_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    json_files["clock.json"] = _freeze_clock_state_for_backup(json.loads(json_files["clock.json"]), snapshot_ms)
    for name, raw in json_files.items():
        with os.fdopen(open_private_file(snapshot_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output:
            output.write(raw)

    upload_root = data_dir / "uploads"
    upload_paths = []
    if upload_root.is_symlink():
        raise BackupError("Cannot back up a symbolic-link uploads directory")
    if upload_root.exists():
        for path in upload_root.rglob("*"):
            if path.is_symlink():
                raise BackupError(f"Cannot back up a symbolic link: {path.relative_to(data_dir)}")
            if path.is_file():
                if path.name.endswith(".tmp"):
                    continue
                upload_paths.append(path)
            elif not path.is_dir():
                raise BackupError(f"Unsupported upload entry: {path.relative_to(data_dir)}")

    upload_paths.sort(key=lambda path: path.relative_to(data_dir).as_posix())
    if len(JSON_MODELS) + len(upload_paths) > MAX_FILES:
        raise BackupError("Too many files to include in backup")
    expected_uploads = _upload_references(json_files)
    found_uploads = {path.relative_to(data_dir).as_posix() for path in upload_paths}
    if not expected_uploads.issubset(found_uploads):
        missing = sorted(expected_uploads - found_uploads)
        raise BackupError(f"A referenced upload is missing: {missing[0]}")

    total_size = sum(map(len, json_files.values()))
    for source in upload_paths:
        target = snapshot_dir / source.relative_to(data_dir)
        secure_directory(target.parent)
        with source.open("rb") as input_file, os.fdopen(open_private_file(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output_file:
            while chunk := input_file.read(CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > MAX_UNPACKED_BYTES:
                    raise BackupError("Backup data exceeds the 1 GiB limit")
                output_file.write(chunk)


def _write_backup_archive(data_dir, destination):
    """Write a ZIP from a stable snapshot directory."""
    json_files = _json_sources(data_dir)
    upload_root = data_dir / "uploads"
    upload_paths = [path for path in upload_root.rglob("*") if path.is_file()] if upload_root.exists() else []
    upload_paths.sort(key=lambda path: path.relative_to(data_dir).as_posix())

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise BackupError("Refusing to write a backup through a symbolic link")
    manifest_files = []
    total_size = 0
    try:
        if os.name == "posix":
            descriptor = open_private_file(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
            )
            os.close(descriptor)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for name, raw in json_files.items():
                if len(raw) > MAX_JSON_BYTES:
                    raise BackupError(f"JSON file is too large: {name}")
                archive.writestr(name, raw)
                total_size += len(raw)
                manifest_files.append({"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

            for path in upload_paths:
                name = path.relative_to(data_dir).as_posix()
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as source, archive.open(name, "w", force_zip64=True) as target:
                    while chunk := source.read(CHUNK_SIZE):
                        size += len(chunk)
                        total_size += len(chunk)
                        if total_size > MAX_UNPACKED_BYTES:
                            raise BackupError("Backup data exceeds the 1 GiB limit")
                        digest.update(chunk)
                        target.write(chunk)
                manifest_files.append({"path": name, "size": size, "sha256": digest.hexdigest()})

            manifest = {
                "format": BACKUP_FORMAT,
                "version": BACKUP_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": manifest_files,
            }
            archive.writestr("manifest.json", _json_bytes(manifest))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if destination.stat().st_size > MAX_ARCHIVE_BYTES:
        destination.unlink(missing_ok=True)
        raise BackupError("Compressed backup exceeds the 512 MiB limit")
    return destination


def create_backup(data_dir, destination):
    """Write a point-in-time ZIP of persisted JSON and upload files."""
    data_dir = Path(data_dir)
    destination = Path(destination)
    with tempfile.TemporaryDirectory(prefix="hamartia-backup-snapshot-") as temp_root:
        snapshot_dir = Path(temp_root)
        with data_mutation_guard(data_dir):
            secure_data_tree(data_dir)
            _capture_backup_snapshot(data_dir, snapshot_dir)
        return _write_backup_archive(snapshot_dir, destination)


def _archive_name(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise BackupError("Invalid path in backup archive")
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(part in ("", ".", "..") for part in path.parts):
        raise BackupError("Invalid path in backup archive")
    if name == "manifest.json" or name in JSON_MODELS:
        return name
    if name.startswith("uploads/") and len(path.parts) > 1:
        return path.as_posix()
    raise BackupError(f"Unexpected file in backup archive: {name}")


def extract_backup(archive_path, destination):
    """Validate an archive fully and extract only its declared regular files."""
    archive_path = Path(archive_path)
    destination = Path(destination)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise BackupError("Compressed backup exceeds the 512 MiB limit")
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise BackupError(f"Invalid ZIP backup: {exc}") from exc

    with archive:
        infos = archive.infolist()
        names = [_archive_name(info.filename) for info in infos]
        if len(names) > MAX_FILES + 1 or len(set(names)) != len(names):
            raise BackupError("Backup contains too many or duplicate entries")
        required = set(JSON_MODELS) - OPTIONAL_BACKUP_JSON
        if "manifest.json" not in names or not required.issubset(names):
            raise BackupError("Backup is incomplete")
        if any(info.is_dir() for info in infos):
            raise BackupError("Directory entries are not allowed in backups")
        total_size = sum(info.file_size for info in infos)
        if total_size > MAX_UNPACKED_BYTES + MAX_MANIFEST_BYTES:
            raise BackupError("Uncompressed backup exceeds the 1 GiB limit")
        for info in infos:
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if stat.S_ISLNK(mode) or file_type not in (0, stat.S_IFREG):
                raise BackupError(f"Non-regular file in backup: {info.filename}")
            if info.filename == "manifest.json" and info.file_size > MAX_MANIFEST_BYTES:
                raise BackupError("Backup manifest is too large")
            if info.filename in JSON_MODELS and info.file_size > MAX_JSON_BYTES:
                raise BackupError(f"JSON file is too large: {info.filename}")

        try:
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise BackupError("Backup manifest must be a JSON object")
            if manifest.get("format") != BACKUP_FORMAT or manifest.get("version") != BACKUP_VERSION:
                raise BackupError("Unsupported Hamartia backup format")
            declared = manifest.get("files")
            if not isinstance(declared, list):
                raise BackupError("Backup manifest has no file list")
            expected = {}
            for entry in declared:
                if not isinstance(entry, dict):
                    raise BackupError("Invalid entry in backup manifest")
                name = _archive_name(entry.get("path"))
                if name == "manifest.json" or name in expected:
                    raise BackupError("Duplicate or invalid entry in backup manifest")
                expected[name] = entry
            if set(expected) != set(names) - {"manifest.json"}:
                raise BackupError("Backup manifest does not match its contents")

            secure_directory(destination)
            for name, entry in expected.items():
                if not isinstance(entry.get("size"), int) or not isinstance(entry.get("sha256"), str):
                    raise BackupError(f"Invalid size or digest for {name}")
                if entry["size"] < 0 or len(entry["sha256"]) != 64:
                    raise BackupError(f"Invalid size or digest for {name}")
                target = destination.joinpath(*PurePosixPath(name).parts)
                secure_directory(target.parent)
                digest = hashlib.sha256()
                size = 0
                with archive.open(name) as source, os.fdopen(open_private_file(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output:
                    while chunk := source.read(CHUNK_SIZE):
                        size += len(chunk)
                        digest.update(chunk)
                        output.write(chunk)
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise BackupError(f"Checksum or size mismatch for {name}")

            for name in OPTIONAL_BACKUP_JSON - set(expected):
                with os.fdopen(open_private_file(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output:
                    output.write(_json_bytes(_defaults()[name]))

            clock_path = destination / "clock.json"
            clock_state = ClockState.model_validate_json(clock_path.read_bytes())
            restored_clock = _prepare_clock_state_for_restore(
                clock_state,
                int(datetime.now(timezone.utc).timestamp() * 1000),
            )
            clock_path.write_bytes(_json_bytes(restored_clock.model_dump(mode="json")))

            json_files = {name: (destination / name).read_bytes() for name in JSON_MODELS}
            for name, raw in json_files.items():
                _validate_json(name, raw)
            references = _upload_references(json_files)
            if not references.issubset(set(expected)):
                raise BackupError("Backup is missing a referenced question or study document")
            secure_data_tree(destination)
            return manifest
        except (json.JSONDecodeError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
            if isinstance(exc, BackupError):
                raise
            raise BackupError(f"Invalid backup archive: {exc}") from exc


def _snapshot_path(data_dir):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return data_dir.with_name(f"{data_dir.name}.before-restore-{stamp}")


def restore_backup(archive_path, data_dir):
    """Restore a validated archive while the API is stopped; retain old data."""
    data_dir = Path(data_dir)
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    with DataDirectoryLock(data_dir):
        if data_dir.is_symlink():
            raise BackupError("Refusing to replace a symbolic-link data directory")
        if data_dir.exists() and not data_dir.is_dir():
            raise BackupError("Data directory path is not a directory")
        secure_data_tree(data_dir)
        with tempfile.TemporaryDirectory(prefix=f".{data_dir.name}.restore-", dir=data_dir.parent) as temp_root:
            staged = Path(temp_root) / "data"
            manifest = extract_backup(archive_path, staged)
            settings_path = data_dir / "settings.json"
            current_key = ""
            if settings_path.exists():
                current = _validate_json("settings.json", settings_path.read_bytes())
                current_key = Settings.model_validate(current).api_key
            restored_settings_path = staged / "settings.json"
            restored_settings = Settings.model_validate_json(restored_settings_path.read_bytes())
            restored_settings.api_key = current_key
            restored_settings_path.write_bytes(_json_bytes(restored_settings.model_dump(mode="json")))

            snapshot = _snapshot_path(data_dir) if data_dir.exists() else None
            if snapshot:
                data_dir.rename(snapshot)
            try:
                staged.rename(data_dir)
            except Exception as error:
                if snapshot and snapshot.exists():
                    snapshot.rename(data_dir)
                raise BackupError(f"Could not apply backup; previous data was restored: {error}") from error
            return {"manifest": manifest, "snapshot": str(snapshot) if snapshot else ""}
