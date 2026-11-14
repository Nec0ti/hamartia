import unittest
from datetime import date, timedelta

from app.core.review_schedule import review_state
from app.core.study_plan import topic_priorities
from app.models.schemas import Question, ReviewAttempt


def question(*attempts, reviewed_at=""):
    return Question(
        id="q1", image_name="q.png", image_path="uploads/q.png",
        subject="Matematik", topic="Fonksiyon", reviewed_at=reviewed_at,
        review_attempts=list(attempts),
    )


class ReviewScheduleTests(unittest.TestCase):
    def test_new_question_is_due_and_legacy_review_flag_stays_archived(self):
        today = date(2026, 11, 14)

        self.assertTrue(review_state(question(), today)["due"])
        self.assertFalse(review_state(question(reviewed_at="2026-11-13T10:00:00Z"), today)["due"])
        self.assertFalse(review_state(question(
            ReviewAttempt(attempted_at="2026-11-13T10:00:00Z", correct=True),
            reviewed_at="2026-11-13T11:00:00Z",
        ), today)["due"])

    def test_wrong_answer_is_due_next_day_and_resets_correct_streak(self):
        today = date(2026, 11, 14)
        state = review_state(question(
            ReviewAttempt(attempted_at="2026-11-13T10:00:00Z", correct=True),
            ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=False),
        ), today)

        self.assertEqual(state, {
            "due_date": "2026-11-15", "due": False, "streak": 0, "last_correct": False,
        })
        self.assertTrue(review_state(question(
            ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=False),
        ), today + timedelta(days=1))["due"])

    def test_consecutive_correct_answers_expand_review_intervals(self):
        today = date(2026, 11, 14)
        state = review_state(question(
            ReviewAttempt(attempted_at="2026-11-10T10:00:00Z", correct=True),
            ReviewAttempt(attempted_at="2026-11-11T10:00:00Z", correct=True),
            ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=True),
        ), today)

        self.assertEqual(state, {
            "due_date": "2026-11-21", "due": False, "streak": 3, "last_correct": True,
        })
        self.assertTrue(review_state(question(
            ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=True),
        ), today + timedelta(days=1))["due"])

    def test_invalid_legacy_attempt_date_is_due_now(self):
        state = review_state(question(
            ReviewAttempt(attempted_at="invalid", correct=True),
        ), date(2026, 11, 14))

        self.assertTrue(state["due"])
        self.assertEqual(state["due_date"], "2026-11-14")

    def test_insights_return_due_questions_and_count_future_reviews(self):
        today = date(2026, 11, 14)
        due = question()
        future = Question(
            id="q2", image_name="q2.png", image_path="uploads/q2.png",
            subject="Matematik", topic="Fonksiyon",
            review_attempts=[ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=True)],
        )

        plan = topic_priorities([due, future], today=today)

        self.assertEqual(plan["pending_questions"], 1)
        self.assertEqual(plan["scheduled_questions"], 1)
        self.assertEqual([item["id"] for item in plan["reviews"]], ["q1"])
        self.assertEqual(plan["topics"][0]["pending_count"], 1)


if __name__ == "__main__":
    unittest.main()
