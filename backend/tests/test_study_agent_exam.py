import tempfile
import unittest
import uuid
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import exams
from app.api import study_agent
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Exam, ExamDeletedApprovalLedger, ExamScoringProfile, Settings, legacy_yks_profile
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService
from app.services.study_agent_exam import (
    EXAM_FIELDS,
    ExamQuote,
    issue_exam_state_token,
    prepare_exam_capture,
    provider_tool_parameters,
    resolve_exam_state_token,
)
from unittest.mock import AsyncMock


class StudyAgentExamTests(unittest.TestCase):
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

    def claim(self, field, quote):
        return {"field": field, "quote": quote}

    def profile(self):
        return legacy_yks_profile()

    def draft(self, messages, field, quote=None, state_token=None, profile=None, language="en"):
        return self.client.post("/exams/agent-draft", json={
            "messages": messages,
            "language": language,
            "expected_exam_field": field,
            "state_token": state_token,
            "scoring_profile_id": (profile or self.profile()).profile_id,
            "scoring_profile_version": (profile or self.profile()).version,
            "evidence_claims": [] if quote is None else [self.claim(field, quote)],
        })

    def complete_flow(self, approval_id=None, language="en"):
        values = ["2026-11-16", "Biology", "25", "3", "2", "55", "0"]
        messages = []
        token = None
        result = None
        profile = self.profile()
        for field, value in zip(EXAM_FIELDS, values, strict=True):
            messages.append(value)
            result = self.draft(messages, field, value, token, profile, language)
            if result.status_code != 200:
                return result, messages, profile
            draft = result.json()
            token = draft["state_token"]
        return result, messages, profile

    def create_body(self, draft, messages, profile, approval_id=None):
        return {
            "messages": messages,
            "language": "en",
            "expected_exam_field": "duration_seconds",
            "state_token": None,
            "scoring_profile_id": profile.profile_id,
            "scoring_profile_version": profile.version,
            "evidence_claims": draft["evidence_claims"],
            "fields": draft["fields"],
            "evidence": draft["verified_evidence"],
            "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
            "derived": draft["derived"],
            "preview_digest": draft["preview_digest"],
            "approval_id": str(approval_id or uuid.uuid4()),
        }

    def rows(self):
        return self.storage.load_list("exams.json", Exam)

    def test_provider_contract_contains_only_field_and_quote_hints(self):
        schema = provider_tool_parameters()
        item = schema["properties"]["evidence"]["items"]
        self.assertEqual(schema["required"], ["evidence"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(item["required"], ["field", "quote"])
        self.assertEqual(set(item["properties"]), {"field", "quote"})
        self.assertEqual(item["properties"]["field"]["enum"], list(EXAM_FIELDS))
        with self.assertRaises(ValueError):
            ExamQuote.model_validate({"field": "correct", "quote": "24", "value": 24})

    def test_parser_requires_explicit_single_field_answers_and_never_defaults_date_or_time(self):
        profile = self.profile()
        first = prepare_exam_capture(["2026-11-16"], "en", [], [self.claim("date", "2026-11-16")], profile)
        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(first["expected_field"], "subject")
        self.assertIn("subject", first["questions"][0].lower())
        self.assertEqual(first["fields"]["date"], "2026-11-16")
        self.assertIsNone(first["fields"]["duration_minutes"])

        for invalid_date in ("today", "yesterday", "2026-02-30", "Maybe 2026-11-16"):
            with self.subTest(invalid_date=invalid_date):
                invalid = prepare_exam_capture([invalid_date], "en", [], [self.claim("date", invalid_date)], profile)
                self.assertEqual(invalid["status"], "ambiguous")
                self.assertIsNone(invalid["preview_digest"])
                self.assertEqual(invalid["evidence_claims"], [])

        for invalid_number in ("-1", "+1", "1 or 2", "maybe 4", "1.5"):
            with self.subTest(invalid_number=invalid_number):
                invalid = prepare_exam_capture([invalid_number], "en", [], [self.claim("date", invalid_number)], profile)
                self.assertEqual(invalid["status"], "ambiguous")
                self.assertIsNone(invalid["preview_digest"])

    def test_subject_and_count_values_are_bound_to_the_exact_expected_turn(self):
        profile = self.profile()
        prior = [{"field": "date", "quote": "2026-11-16", "message_index": 0}]
        mismatched = prepare_exam_capture(
            ["2026-11-16", "Biology", "25"], "en", prior,
            [self.claim("subject", "Biology")], profile,
        )
        self.assertEqual(mismatched["status"], "ambiguous")
        self.assertEqual(mismatched["evidence_claims"], prior)
        self.assertIsNone(mismatched["preview_digest"])

        uncertain = prepare_exam_capture(
            ["2026-11-16", "not sure"], "en", prior,
            [self.claim("subject", "not sure")], profile,
        )
        self.assertEqual(uncertain["status"], "ambiguous")
        self.assertEqual(uncertain["evidence_claims"], prior)

    def test_state_token_is_bound_to_transcript_language_profile_and_one_use(self):
        messages = ["2026-11-16"]
        profile = self.profile()
        claims = [{"field": "date", "quote": messages[0], "message_index": 0}]
        token = issue_exam_state_token(messages, "en", claims, profile.profile_id, profile.version)
        self.assertEqual(resolve_exam_state_token(token, [*messages, "Biology"], "en", profile.profile_id, profile.version), claims)
        with self.assertRaises(ValueError):
            resolve_exam_state_token(token, [*messages, "Chemistry"], "en", profile.profile_id, profile.version)

        for kwargs in (
            {"language": "tr", "profile_id": profile.profile_id, "profile_version": profile.version},
            {"language": "en", "profile_id": "forged", "profile_version": profile.version},
            {"language": "en", "profile_id": profile.profile_id, "profile_version": profile.version + 1},
        ):
            fresh = issue_exam_state_token(messages, "en", claims, profile.profile_id, profile.version)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                resolve_exam_state_token(
                    fresh, [*messages, "Biology"], kwargs["language"],
                    kwargs["profile_id"], kwargs["profile_version"],
                )

        fresh = issue_exam_state_token(messages, "en", claims, profile.profile_id, profile.version)
        with self.assertRaises(ValueError):
            resolve_exam_state_token(fresh + "!!!", [*messages, "Biology"], "en", profile.profile_id, profile.version)
        with self.assertRaises(ValueError):
            resolve_exam_state_token(fresh, messages, "en", profile.profile_id, profile.version)

    def test_draft_route_never_writes_and_follows_expected_turns(self):
        first = self.draft(["2026-11-16"], "date", "2026-11-16")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "incomplete")
        self.assertEqual(first.json()["expected_field"], "subject")
        self.assertFalse(first.json()["write_allowed"])
        self.assertEqual(self.rows(), [])

        wrong_field = self.draft(["2026-11-16", "Biology"], "correct", "Biology", first.json()["state_token"])
        self.assertEqual(wrong_field.status_code, 409, wrong_field.text)
        fresh_first = self.draft(["2026-11-16"], "date", "2026-11-16")
        wrong_quote = self.draft(["2026-11-16", "Biology"], "subject", "Chemistry", fresh_first.json()["state_token"])
        self.assertEqual(wrong_quote.status_code, 200, wrong_quote.text)
        self.assertEqual(wrong_quote.json()["status"], "ambiguous")
        self.assertIsNone(wrong_quote.json()["preview_digest"])
        self.assertEqual(self.rows(), [])

    def test_exact_preview_approval_is_idempotent_and_changed_replay_conflicts(self):
        response, messages, profile = self.complete_flow()
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        self.assertEqual(draft["status"], "ready")
        self.assertEqual(draft["fields"]["exam_type"], "branch")
        self.assertEqual(draft["fields"]["scoring_profile_id"], profile.profile_id)
        self.assertEqual(draft["derived"]["net"], 24.25)
        self.assertFalse(draft["write_allowed"])
        self.assertEqual(self.rows(), [])

        approval_id = uuid.uuid4()
        body = self.create_body(draft, messages, profile, approval_id)
        created = self.client.post("/exams/agent-create", json=body)
        self.assertEqual(created.status_code, 201, created.text)
        saved = created.json()
        self.assertEqual(saved["exam_type"], "branch")
        self.assertEqual(saved["subject"], "Biology")
        self.assertEqual(len(self.rows()), 1)
        replay = self.client.post("/exams/agent-create", json=body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], saved["id"])
        self.assertEqual(len(self.rows()), 1)

        altered = dict(body)
        altered["fields"] = dict(body["fields"], correct=24)
        conflict = self.client.post("/exams/agent-create", json=altered)
        self.assertEqual(conflict.status_code, 422, conflict.text)
        self.assertEqual(len(self.rows()), 1)

    def test_concurrent_same_approval_creates_one_row_and_delete_tombstone_blocks_replay(self):
        response, messages, profile = self.complete_flow()
        self.assertEqual(response.status_code, 200, response.text)
        body = self.create_body(response.json(), messages, profile)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.client.post("/exams/agent-create", json=body), range(8)))
        self.assertTrue(all(result.status_code == 201 for result in results), [result.text for result in results])
        self.assertEqual(len(self.rows()), 1)
        record_id = results[0].json()["id"]
        deleted = self.client.delete(f"/exams/{record_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.rows(), [])
        ledger = self.storage.load_doc("exam_agent_approvals.json", ExamDeletedApprovalLedger)
        self.assertEqual(ledger.approval_ids, [uuid.UUID(body["approval_id"])])
        replay = self.client.post("/exams/agent-create", json=body)
        self.assertEqual(replay.status_code, 409, replay.text)
        self.assertEqual(self.rows(), [])

    def test_custom_profile_is_host_selected_and_profile_changes_invalidate_draft(self):
        custom = ExamScoringProfile(
            profile_id="custom", version=1, display_name="Custom", country_label="Test",
            scoring_rule={"correct_points": "1/1", "wrong_penalty": "1/2", "blank_points": "0/1"},
        )
        self.storage.append_list("exam_profiles.json", custom, ExamScoringProfile)
        initial = self.draft(["2026-11-16"], "date", "2026-11-16", profile=custom)
        self.assertEqual(initial.status_code, 200, initial.text)
        changed_profile = ExamScoringProfile(
            profile_id="custom", version=2, display_name="Custom v2", country_label="Test",
            scoring_rule={"correct_points": "1/1", "wrong_penalty": "1/3", "blank_points": "0/1"},
        )
        self.storage.append_list("exam_profiles.json", changed_profile, ExamScoringProfile)
        changed = self.draft(
            ["2026-11-16", "Biology"], "subject", "Biology", initial.json()["state_token"],
            profile=changed_profile,
        )
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(self.rows(), [])

    def test_composed_configured_provider_binds_latest_turn_and_host_selected_profile(self):
        endpoint = "https://provider.example/v1"
        self.storage.save_doc("settings.json", Settings(
            litellm_base_url=endpoint, model_name="mock-model", api_key="",
        ))
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(study_agent.router)
        profile = self.profile()
        with patch.object(study_agent, "DATA_DIR", self.data_dir), patch.object(study_agent, "AIService") as service:
            fake = service.return_value
            fake.base_url = endpoint
            fake.study_exam_prepare = AsyncMock(return_value={
                "current_evidence_claims": [{"field": "date", "quote": "2026-11-16"}],
            })
            with TestClient(app) as client:
                first = client.post("/study-agent/local", json={
                    "consent": True, "message": "2026-11-16", "context": "", "language": "en",
                    "endpoint": endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": "exam-entry", "expected_exam_field": "date",
                    "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version,
                    "messages": ["2026-11-16"],
                })
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["expected_field"], "subject")
                self.assertEqual(first.json()["status"], "incomplete")
                self.assertEqual(self.rows(), [])
                fake.study_exam_prepare.assert_awaited_once_with(["2026-11-16"], "en", "date")

                fake.study_exam_prepare = AsyncMock(return_value={
                    "current_evidence_claims": [{"field": "subject", "quote": "2026-11-16"}],
                })
                stale = client.post("/study-agent/local", json={
                    "consent": True, "message": "Biology", "context": "", "language": "en",
                    "endpoint": endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": "exam-entry", "expected_exam_field": "subject",
                    "exam_state_token": first.json()["state_token"],
                    "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version,
                    "messages": ["2026-11-16", "Biology"],
                })
                self.assertEqual(stale.status_code, 200, stale.text)
                self.assertEqual(stale.json()["status"], "ambiguous")
                self.assertIsNone(stale.json()["preview_digest"])
                self.assertEqual(self.rows(), [])

    def test_deleted_exam_ledger_survives_backup_and_legacy_backups_default_empty(self):
        response, messages, profile = self.complete_flow()
        self.assertEqual(response.status_code, 200, response.text)
        body = self.create_body(response.json(), messages, profile)
        saved = self.client.post("/exams/agent-create", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.client.delete(f"/exams/{saved.json()['id']}")
        archive = Path(self.temp.name) / "snapshot.zip"
        restored = Path(self.temp.name) / "restored"
        create_backup(self.data_dir, archive)
        restore_backup(archive, restored)
        ledger = StorageService(restored).load_doc("exam_agent_approvals.json", ExamDeletedApprovalLedger)
        self.assertEqual(ledger.approval_ids, [uuid.UUID(body["approval_id"])])

        # A pre-feature backup omits the optional approval ledger entirely.
        legacy_archive = Path(self.temp.name) / "legacy-snapshot.zip"
        with zipfile.ZipFile(archive) as source:
            entries = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
            manifest = json.loads(source.read("manifest.json"))
        entries.pop("exam_agent_approvals.json")
        manifest["files"] = [item for item in manifest["files"] if item["path"] != "exam_agent_approvals.json"]
        with zipfile.ZipFile(legacy_archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, raw in entries.items():
                target.writestr(name, raw)
            target.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
        legacy_restored = Path(self.temp.name) / "legacy-restored"
        restore_backup(legacy_archive, legacy_restored)
        empty_ledger = StorageService(legacy_restored).load_doc("exam_agent_approvals.json", ExamDeletedApprovalLedger)
        self.assertEqual(empty_ledger.approval_ids, [])

    def test_agent_create_rejects_more_evidence_quotes_than_exam_fields(self):
        response, messages, profile = self.complete_flow()
        self.assertEqual(response.status_code, 200, response.text)
        body = self.create_body(response.json(), messages, profile)
        body["evidence_claims"] = body["evidence_claims"] + body["evidence_claims"][:2]
        result = self.client.post("/exams/agent-create", json=body)
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
