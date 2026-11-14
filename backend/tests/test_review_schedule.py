import unittest
from datetime import date, timedelta

from app.core.review_schedule import review_state
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question, ReviewAttempt


def question(*attempts, reviewed_at=""):
    return Question(
        id="q1", image_name="q.png", image_path="uploads/q.png",
        subject="Matematik", topic="Fonksiyon", reviewed_at=reviewed_at,
        review_attempts=list(attempts),
    )


class ReviewScheduleTests(unittest.TestCase):
    def test_question_order_insights_bucket_wrong_records_and_use_median_time(self):
        exam = Exam(id="e1", date="2026-11-14", subject="Matematik", correct=7, incorrect=2, blank=1)
        questions = [
            Question(id="q1", exam_id="e1", solve_order=1, time_spent_seconds=20),
            Question(id="q2", exam_id="e1", solve_order=2, time_spent_seconds=40),
            Question(id="q3", exam_id="e1", solve_order=5, time_spent_seconds=15),
            Question(id="q4", exam_id="e1", solve_order=10, time_spent_seconds=60),
            Question(id="orphan", exam_id="deleted", solve_order=1, time_spent_seconds=10),
            Question(id="untracked", exam_id="e1", time_spent_seconds=99),
        ]

        order = topic_priorities(questions, exams=[exam])["question_order"]

        self.assertEqual(len(order), 1)
        self.assertEqual(order[0]["exam_count"], 1)
        self.assertEqual(order[0]["early"], {"wrong_count": 2, "median_seconds": 30})
        self.assertEqual(order[0]["middle"], {"wrong_count": 1, "median_seconds": 15})
        self.assertEqual(order[0]["late"], {"wrong_count": 1, "median_seconds": 60})

    def test_order_insights_empty_when_exam_is_deleted(self):
        question_with_old_exam = Question(id="q1", exam_id="deleted", solve_order=1, time_spent_seconds=10)

        self.assertEqual(topic_priorities([question_with_old_exam])["question_order"], [])

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

    def test_insights_count_distinct_questions_and_each_todays_outcome(self):
        today = date(2026, 11, 14)
        first = question(
            ReviewAttempt(attempted_at="2026-11-14T09:00:00Z", correct=False),
            ReviewAttempt(attempted_at="2026-11-14T09:05:00Z", correct=True),
        )
        second = Question(
            id="q2", subject="Fizik", topic="Vektör",
            review_attempts=[ReviewAttempt(attempted_at="2026-11-14T10:00:00Z", correct=False)],
        )
        old = Question(
            id="q3", review_attempts=[ReviewAttempt(attempted_at="2026-11-13T23:59:00Z", correct=True)],
        )

        plan = topic_priorities([first, second, old], today=today)

        self.assertEqual(plan["today_questions"], 2)
        self.assertEqual(plan["today_correct"], 1)
        self.assertEqual(plan["today_incorrect"], 2)

    def test_insights_ignore_invalid_attempt_dates_for_todays_activity(self):
        plan = topic_priorities([question(
            ReviewAttempt(attempted_at="invalid", correct=True),
        )], today=date(2026, 11, 14))

        self.assertEqual((plan["today_questions"], plan["today_correct"], plan["today_incorrect"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
