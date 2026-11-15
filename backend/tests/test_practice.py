import asyncio
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.api import practice
from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession, PracticeSessionCreate
from app.services.storage import StorageService


def payload(**updates):
    values = dict(
        date="2026-11-14", subject="Matematik", topic="Fonksiyon",
        correct=6, incorrect=2, blank=1, duration_minutes=15,
    )
    values.update(updates)
    return PracticeSessionCreate(**values)


class PracticeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = StorageService(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_net_accuracy_and_blank_denominator(self):
        session = PracticeSession(id="s1", **payload().model_dump())

        self.assertEqual(session.net, 5.5)
        self.assertEqual(session.accuracy, 0.75)
        blank_only = PracticeSession(id="s2", **payload(correct=0, incorrect=0, blank=4).model_dump())
        self.assertIsNone(blank_only.accuracy)

    def test_input_rejects_empty_labels_invalid_date_negative_and_empty_set(self):
        for values in (
            {"subject": " "}, {"topic": " "}, {"date": "14-11-2026"},
            {"correct": -1}, {"correct": 0, "incorrect": 0, "blank": 0},
            {"duration_seconds": 60},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                payload(**values)

    def test_legacy_missing_file_is_empty(self):
        self.assertEqual(asyncio.run(practice.list_sessions(self.storage)), [])

    def test_create_update_delete_persist_sessions_and_preserve_identity(self):
        created = asyncio.run(practice.create_session(payload(), self.storage, None))
        self.assertTrue(created.id.startswith("practice_"))
        self.assertEqual(len(asyncio.run(practice.list_sessions(self.storage))), 1)

        updated_payload = payload(correct=8, incorrect=0, blank=1)
        updated = asyncio.run(practice.update_session(created.id, updated_payload, self.storage))
        self.assertEqual((updated.id, updated.created_at, updated.correct), (created.id, created.created_at, 8))

        result = asyncio.run(practice.delete_session(created.id, self.storage))
        self.assertEqual(result, {"deleted": created.id})
        self.assertEqual(asyncio.run(practice.list_sessions(self.storage)), [])

    def test_focus_completion_idempotency_prevents_duplicate_on_retry(self):
        key = str(uuid4())
        completed = asyncio.run(practice.create_session(payload(), self.storage, key))
        retried = asyncio.run(practice.create_session(payload(), self.storage, key))
        self.assertEqual(retried.id, completed.id)
        self.assertEqual(len(asyncio.run(practice.list_sessions(self.storage))), 1)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(practice.create_session(payload(correct=7), self.storage, key))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(asyncio.run(practice.list_sessions(self.storage))), 1)

    def test_update_missing_session_returns_404(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(practice.update_session("missing", payload(), self.storage))
        self.assertEqual(error.exception.status_code, 404)

    def test_summary_groups_normalized_labels_and_sorts_trend(self):
        sessions = [
            PracticeSession(id="later", created_at="b", **payload(date="2026-11-14", correct=8, incorrect=0).model_dump()),
            PracticeSession(id="earlier", created_at="a", **payload(date="2026-11-01", subject=" matematik ", correct=4, incorrect=4).model_dump()),
            PracticeSession(id="blank", created_at="c", **payload(date="2026-11-14", correct=0, incorrect=0, blank=5).model_dump()),
        ]

        summary = practice_topic_summaries(sessions)

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["session_count"], 3)
        self.assertEqual(summary[0]["answered"], 16)
        self.assertEqual(summary[0]["correct"], 12)
        self.assertEqual(summary[0]["accuracy"], 0.75)
        self.assertEqual([item["id"] for item in summary[0]["trend"]], ["earlier", "later", "blank"])
        self.assertEqual(summary[0]["trend"][2]["accuracy"], None)


if __name__ == "__main__":
    unittest.main()
