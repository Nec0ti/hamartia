import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import exams
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Exam, ExamDeletedApprovalLedger, legacy_yks_profile
from app.services.storage import StorageService
from app.services.backup import create_backup, restore_backup
from app.services.study_agent_exam import issue_exam_state_token
from app.services.study_agent_sectioned_exam import MAX_SECTIONS, resolve_state_token


class StudyAgentSectionedExamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.storage = StorageService(self.data_dir)
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(exams.router)
        self.data_patch = patch.object(exams, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def field_list(count):
        return ["exam_type", "date", "duration_minutes", "duration_seconds", "section_count"] + [
            f"section_{index}_{field}" for index in range(1, count + 1) for field in ("subject", "correct", "incorrect", "blank")
        ]

    def draft(self, messages, field, quote, token=None, language="en"):
        profile = legacy_yks_profile()
        return self.client.post("/exams/sectioned-agent-draft", json={
            "messages": messages, "language": language, "expected_exam_field": field, "state_token": token,
            "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version,
            "evidence_claims": [] if quote is None else [{"field": field, "quote": quote}],
        })

    def complete(self, count=1, language="en", invalid=None):
        fields = self.field_list(count)
        values = ["TYT", "2026-11-16", "90", "0", str(count)]
        for index in range(1, count + 1):
            values.extend([f"Subject {index}", "10", "2", "3"])
        messages, token, draft = [], None, None
        for field, value in zip(fields, values, strict=True):
            if invalid == field:
                messages.append("not a supported value")
                response = self.draft(messages, field, messages[-1], token, language)
                self.assertEqual(response.status_code, 200, response.text)
                draft, token = response.json(), response.json()["state_token"]
            messages.append(value)
            response = self.draft(messages, field, value, token, language)
            self.assertEqual(response.status_code, 200, response.text)
            draft, token = response.json(), response.json()["state_token"]
        self.assertEqual(draft["status"], "ready")
        return draft, messages

    def create_body(self, draft, messages, approval_id=None):
        return {
            "messages": messages, "language": "en",
            "expected_exam_field": draft["evidence_claims"][-1]["field"], "state_token": None,
            "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1,
            "evidence_claims": draft["evidence_claims"], "fields": draft["fields"],
            "evidence": draft["verified_evidence"], "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
            "derived": draft["derived"], "preview_digest": draft["preview_digest"],
            "approval_id": str(approval_id or uuid.uuid4()),
        }

    def rows(self):
        return self.storage.load_list("exams.json", Exam)

    def test_explicit_section_flow_persists_exact_totals_and_profile_then_idempotently_retries(self):
        draft, messages = self.complete()
        self.assertEqual(draft["fields"]["sections"], [{"subject": "Subject 1", "correct": 10, "incorrect": 2, "blank": 3}])
        self.assertEqual(draft["fields"]["correct"], 10)
        body = self.create_body(draft, messages)
        saved = self.client.post("/exams/sectioned-agent-create", json=body)
        retry = self.client.post("/exams/sectioned-agent-create", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(saved.json(), retry.json())
        self.assertEqual(saved.json()["sections"], draft["fields"]["sections"])
        self.assertEqual(saved.json()["scoring_profile"], draft["scoring_profile_snapshot"])
        self.assertEqual(saved.json()["net"], draft["derived"]["net"])
        self.assertEqual(saved.json()["xp"], draft["derived"]["xp"])
        self.assertEqual(len(self.rows()), 1)

    def test_invalid_current_answer_is_followed_up_without_guess_and_can_continue_with_gapped_quotes(self):
        messages = ["YKS"]
        invalid = self.draft(messages, "exam_type", "YKS")
        self.assertEqual(invalid.status_code, 200, invalid.text)
        self.assertEqual(invalid.json()["status"], "ambiguous")
        self.assertNotIn("exam_type", invalid.json()["fields"])
        messages.append("TYT")
        valid = self.draft(messages, "exam_type", "TYT", invalid.json()["state_token"])
        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(valid.json()["evidence_claims"], [{"field": "exam_type", "quote": "TYT", "message_index": 1}])
        self.assertEqual(self.rows(), [])

    def test_six_section_ceiling_and_unique_subject_validation(self):
        values = ["TYT", "2026-11-16", "1", "0", str(MAX_SECTIONS)]
        values.extend([value for index in range(1, MAX_SECTIONS + 1) for value in (f"Subject {index}", "1", "0", "0")])
        draft, _messages = self.complete(MAX_SECTIONS)
        self.assertEqual(len(draft["fields"]["sections"]), MAX_SECTIONS)
        self.assertEqual(len(draft["evidence_claims"]), 5 + 4 * MAX_SECTIONS)
        self.assertEqual(len(values), len(draft["evidence_claims"]))

        # Repeated explicit subject facts cannot silently become a preview.
        messages, token, result = [], None, None
        fields = self.field_list(2)
        duplicate_values = ["AYT", "2026-11-16", "60", "0", "2", "Matematik", "1", "0", "0", "Matematik"]
        for field, value in zip(fields[:10], duplicate_values, strict=True):
            messages.append(value)
            response = self.draft(messages, field, value, token)
            self.assertEqual(response.status_code, 200, response.text)
            result, token = response.json(), response.json()["state_token"]
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["preview_digest"])
        self.assertEqual(self.rows(), [])

    def test_wrong_scope_replay_tampered_totals_and_deleted_approval_are_rejected(self):
        branch_token = issue_exam_state_token(["2026-11-16"], "en", [], "legacy-yks", 1)
        wrong = self.draft(["2026-11-16", "TYT"], "exam_type", "TYT", branch_token)
        self.assertEqual(wrong.status_code, 409)

        draft, messages = self.complete(1, invalid="date")
        body = self.create_body(draft, messages)
        altered = {**body, "fields": {**body["fields"], "correct": 999}}
        bad = self.client.post("/exams/sectioned-agent-create", json=altered)
        self.assertEqual(bad.status_code, 422, bad.text)
        self.assertEqual(self.rows(), [])
        saved = self.client.post("/exams/sectioned-agent-create", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.client.delete(f"/exams/{saved.json()['id']}")
        replay = self.client.post("/exams/sectioned-agent-create", json=body)
        self.assertEqual(replay.status_code, 409)
        ledger = self.storage.load_doc(exams.SECTIONED_AGENT_APPROVALS_FILE, ExamDeletedApprovalLedger)
        self.assertEqual(ledger.approval_ids, [uuid.UUID(body["approval_id"])])
        archive = self.data_dir / "sectioned-snapshot.zip"
        restored = self.data_dir / "restored-sectioned"
        create_backup(self.data_dir, archive)
        restore_backup(archive, restored)
        with patch.object(exams, "DATA_DIR", restored):
            restored_replay = self.client.post("/exams/sectioned-agent-create", json=body)
        self.assertEqual(restored_replay.status_code, 409)
        restored_ledger = StorageService(restored).load_doc(exams.SECTIONED_AGENT_APPROVALS_FILE, ExamDeletedApprovalLedger)
        self.assertEqual(restored_ledger.approval_ids, [uuid.UUID(body["approval_id"])])

    def test_concurrent_same_preview_approval_creates_one_row(self):
        draft, messages = self.complete()
        body = self.create_body(draft, messages)
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.client.post("/exams/sectioned-agent-create", json=body), range(4)))
        self.assertTrue(all(response.status_code == 201 for response in responses), [response.text for response in responses])
        self.assertEqual(len(self.rows()), 1)
