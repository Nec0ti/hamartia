import tempfile
import unittest
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import exams, study_agent
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Exam, ExamDeletedApprovalLedger, Settings
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService
from app.services.study_agent_custom_exam import MAX_MESSAGES, MAX_SECTIONS, _question, issue_state_token


class StudyAgentCustomExamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.storage = StorageService(self.data_dir)
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(exams.router)
        app.include_router(study_agent.router)
        self.data_patch = patch.object(exams, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.study_data_patch = patch.object(study_agent, "DATA_DIR", self.data_dir)
        self.study_data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.study_data_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def field_list(count):
        return ["format_name", "date", "duration_minutes", "duration_seconds", "section_count"] + [
            f"section_{index}_{field}" for index in range(1, count + 1) for field in ("subject", "correct", "incorrect", "blank")
        ]

    def draft(self, messages, field, quote, token=None, language="en"):
        return self.client.post("/exams/custom-sectioned-agent-draft", json={
            "messages": messages, "language": language, "expected_exam_field": field, "state_token": token,
            "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1,
            "evidence_claims": [] if quote is None else [{"field": field, "quote": quote}],
        })

    def complete(self, count=1):
        fields = self.field_list(count)
        values = ["Personal assessment", "2026-11-19", "90", "0", str(count)]
        for index in range(1, count + 1):
            values.extend([f"Learner section {index}", "10", "2", "3"])
        messages, token, draft = [], None, None
        for field, value in zip(fields, values, strict=True):
            messages.append(value)
            response = self.draft(messages, field, value, token)
            self.assertEqual(response.status_code, 200, response.text)
            draft, token = response.json(), response.json()["state_token"]
        self.assertEqual(draft["status"], "ready")
        self.assertLessEqual(len(messages), MAX_MESSAGES)
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

    def test_custom_capture_asks_for_explicit_values_and_saves_verified_preview(self):
        self.assertEqual(_question("section_count", "en"), "Reply with one clear value for section count (1-12).")
        self.assertIn("kendi adı", _question("format_name", "tr"))
        draft, messages = self.complete()
        self.assertEqual(draft["fields"]["exam_type"], "custom")
        self.assertEqual(draft["fields"]["format_name"], "Personal assessment")
        self.assertEqual(draft["fields"]["sections"], [{"subject": "Learner section 1", "correct": 10, "incorrect": 2, "blank": 3}])
        body = self.create_body(draft, messages)
        saved = self.client.post("/exams/custom-sectioned-agent-create", json=body)
        retry = self.client.post("/exams/custom-sectioned-agent-create", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json(), retry.json())
        self.assertEqual(saved.json()["format_name"], "Personal assessment")
        self.assertEqual(saved.json()["subject"], "Personal assessment")
        self.assertEqual(saved.json()["scoring_profile"], draft["scoring_profile_snapshot"])
        self.assertEqual((saved.json()["net"], saved.json()["xp"]), (draft["derived"]["net"], draft["derived"]["xp"]))
        self.assertEqual(len(self.rows()), 1)

    def test_twelve_sections_fit_custom_turn_limit_and_names_remain_distinct(self):
        draft, messages = self.complete(MAX_SECTIONS)
        self.assertEqual(len(messages), 5 + 4 * 12)
        self.assertEqual(len(draft["fields"]["sections"]), 12)
        self.assertEqual(draft["fields"]["correct"], 120)
        self.assertEqual(len(draft["evidence_claims"]), 53)

    def test_uncertain_or_invalid_value_is_not_inferred_and_can_be_corrected(self):
        messages = ["maybe a name"]
        invalid = self.draft(messages, "format_name", messages[0])
        self.assertEqual(invalid.status_code, 200, invalid.text)
        self.assertEqual(invalid.json()["status"], "ambiguous")
        self.assertNotIn("format_name", invalid.json()["fields"])
        messages.append("My own mock")
        corrected = self.draft(messages, "format_name", messages[-1], invalid.json()["state_token"])
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.assertEqual(corrected.json()["fields"]["format_name"], "My own mock")
        self.assertEqual(self.rows(), [])

    def test_wrong_workflow_scope_altered_preview_cancel_delete_replay_and_backup_tombstone(self):
        wrong_token = issue_state_token(["Personal mock"], "en", [], _profile())
        wrong = self.draft(["Personal mock", "2026-11-19"], "date", "2026-11-19", wrong_token)
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(self.rows(), [])

        draft, messages = self.complete()
        body = self.create_body(draft, messages)
        invalid = self.client.post("/exams/custom-sectioned-agent-create", json={**body, "fields": {**body["fields"], "correct": 99}})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(self.rows(), [])
        saved = self.client.post("/exams/custom-sectioned-agent-create", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.client.delete(f"/exams/{saved.json()['id']}")
        replay = self.client.post("/exams/custom-sectioned-agent-create", json=body)
        self.assertEqual(replay.status_code, 409)
        ledger = self.storage.load_doc(exams.CUSTOM_SECTIONED_AGENT_APPROVALS_FILE, ExamDeletedApprovalLedger)
        self.assertEqual(ledger.approval_ids, [uuid.UUID(body["approval_id"])])
        archive = self.data_dir / "custom-snapshot.zip"
        restored = self.data_dir / "restored-custom"
        create_backup(self.data_dir, archive)
        restore_backup(archive, restored)
        with patch.object(exams, "DATA_DIR", restored):
            restored_replay = self.client.post("/exams/custom-sectioned-agent-create", json=body)
        self.assertEqual(restored_replay.status_code, 409)
        restored_ledger = StorageService(restored).load_doc(exams.CUSTOM_SECTIONED_AGENT_APPROVALS_FILE, ExamDeletedApprovalLedger)
        self.assertEqual(restored_ledger.approval_ids, [uuid.UUID(body["approval_id"])])

    def test_concurrent_same_approval_converges_to_one_row(self):
        draft, messages = self.complete()
        body = self.create_body(draft, messages)
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.client.post("/exams/custom-sectioned-agent-create", json=body), range(4)))
        self.assertTrue(all(response.status_code == 201 for response in responses), [response.text for response in responses])
        self.assertEqual(len(self.rows()), 1)

    def test_configured_endpoint_adapter_uses_mock_quote_and_host_validation(self):
        endpoint = "http://127.0.0.1:9444/v1"
        self.storage.save_doc("settings.json", Settings(litellm_base_url=endpoint, model_name="mock-model"))
        fake = type("MockAI", (), {})()
        fake.base_url = endpoint
        fake.study_custom_exam_prepare = AsyncMock(return_value={"current_evidence_claims": [{"field": "format_name", "quote": "Personal mock"}]})
        with patch.object(study_agent, "AIService", return_value=fake) as ai_service:
            response = self.client.post("/study-agent/local", json={
                "consent": True, "message": "Personal mock", "context": "", "language": "en", "endpoint": endpoint,
                "model_name": "mock-model", "has_api_key": False, "workflow": "custom-sectioned-exam-entry",
                "expected_custom_exam_field": "format_name", "custom_exam_state_token": None,
                "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1, "messages": ["Personal mock"],
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["expected_field"], "date")
        fake.study_custom_exam_prepare.assert_awaited_once_with(["Personal mock"], "en", "format_name")
        ai_service.assert_called_once()
        self.assertEqual(self.rows(), [])

    def test_local_cli_requires_full_verified_preview_and_separate_approval(self):
        from app.core import config
        from app.services.study_agent_cli import dispatch_record_command

        fields = self.field_list(2)
        values = ["CLI mock", "2026-11-19", "45", "0", "2",
                  "Reading", "4", "1", "2", "Reasoning", "3", "2", "1"]
        messages, token, draft = [], None, None
        with patch.object(config, "DATA_DIR", self.data_dir):
            for field, value in zip(fields, values, strict=True):
                messages.append(value)
                draft = asyncio.run(dispatch_record_command({
                    "command": "study.custom_sectioned_exam.draft", "messages": messages,
                    "language": "en", "expected_exam_field": field, "state_token": token,
                    "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1,
                    "evidence_claims": [{"field": field, "quote": value}],
                }))
                self.assertFalse(draft["write_allowed"])
                token = draft["state_token"]
            self.assertEqual(draft["status"], "ready")
            self.assertEqual(self.rows(), [])
            saved = asyncio.run(dispatch_record_command({
                "command": "study.custom_sectioned_exam.approve", "approved": True,
                "messages": messages, "language": "en", "expected_exam_field": draft["evidence_claims"][-1]["field"],
                "state_token": None, "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1,
                "evidence_claims": draft["evidence_claims"], "fields": draft["fields"],
                "evidence": draft["verified_evidence"], "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
                "derived": draft["derived"], "preview_digest": draft["preview_digest"], "approval_id": str(uuid.uuid4()),
            }))
        self.assertEqual(saved["status"], "saved")
        self.assertEqual(saved["record"]["format_name"], "CLI mock")
        self.assertEqual(len(self.rows()), 1)


def _profile():
    from app.models.schemas import legacy_yks_profile
    return legacy_yks_profile()
