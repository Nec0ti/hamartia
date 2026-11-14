import asyncio
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.api.cosmos import get_cosmos
from app.api.user import get_user
from app.core.progression import progression_summary
from app.models.schemas import CosmosData, Exam, UserStats
from app.services.storage import StorageService


def exam(index, day):
    return Exam(
        id=f"exam-{index}", date=day.isoformat(), subject="Matematik",
        correct=20, incorrect=3, blank=2, duration_minutes=40,
    )


class ProgressionTests(unittest.TestCase):
    def test_total_xp_level_and_consecutive_exam_streak(self):
        today = date(2026, 11, 14)
        exams = [exam(i, today - timedelta(days=i)) for i in range(3)]
        exams.append(exam(4, today + timedelta(days=1)))

        result = progression_summary(exams, bonus_xp=50, today=today)

        self.assertEqual(result["total_xp"], sum(item.xp for item in exams) + 50)
        self.assertEqual(result["level"], result["total_xp"] // 500 + 1)
        self.assertEqual(result["streak_days"], 3)
        self.assertEqual(result["last_active_date"], today.isoformat())

    def test_streak_expires_after_a_missed_day_and_ignores_bad_legacy_date(self):
        today = date(2026, 11, 14)
        old = exam(1, today - timedelta(days=3))
        invalid = exam(2, today)
        invalid.date = "old-date"

        result = progression_summary([old, invalid], today=today)

        self.assertEqual(result["streak_days"], 0)
        self.assertEqual(result["last_active_date"], old.date)

    def test_no_exams_means_no_active_streak(self):
        result = progression_summary([], bonus_xp=75, today=date(2026, 11, 14))

        self.assertEqual(result, {
            "total_xp": 75, "level": 1, "streak_days": 0, "last_active_date": "",
        })

    def test_profile_and_cosmos_include_exam_xp_and_keep_existing_bonus(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = StorageService(Path(directory))
            saved_exam = exam(1, date(2026, 11, 14))
            storage.save_list("exams.json", [saved_exam])
            storage.save_doc("user.json", UserStats(total_xp=40))
            storage.save_doc("cosmos.json", CosmosData())

            profile = asyncio.run(get_user(storage))
            cosmos = asyncio.run(get_cosmos(storage))

        self.assertEqual(profile.total_xp, saved_exam.xp + 40)
        self.assertEqual(cosmos.user_xp, profile.total_xp)


if __name__ == "__main__":
    unittest.main()
