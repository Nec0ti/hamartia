"""Measure order-aware mistake summaries without loading or calling AI."""

import json
import time

from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question


def measure(count):
    exam = Exam(id="exam", date="2026-11-14", subject="Matematik", correct=75, incorrect=25, blank=20)
    questions = [Question(
        id=f"q{index}", exam_id=exam.id, question_number=index % 120 + 1,
        solve_order=index % 120 + 1, time_spent_seconds=index % 95 + 1,
    ) for index in range(count)]

    started = time.perf_counter()
    summary = topic_priorities(questions, exams=[exam])["question_order"]
    elapsed = time.perf_counter() - started
    assert sum(summary[0][stage]["wrong_count"] for stage in ("early", "middle", "late")) == count
    return {
        "questions": count,
        "summary_seconds": round(elapsed, 6),
        "records_per_second": round(count / elapsed, 2),
    }


if __name__ == "__main__":
    print(json.dumps({
        "benchmark": "question_order_summary",
        "runs": [measure(1_000), measure(10_000)],
        "ai_included": False,
    }))
