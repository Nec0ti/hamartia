"""Measure solve-order summaries over seeded, persisted multi-exam mistakes."""

import argparse
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question
from app.services.storage import StorageService
from benchmark_common import emit, measure

SEED = 20261114
TODAY = date(2026, 11, 14)


def run(counts=(1000, 10000), repeats=7, json_output=None):
    rng = random.Random(SEED)
    results = []
    for count in counts:
        exam_count = max(10, count // 40)
        exams = [Exam(
            id=f"exam-{index}", date=(TODAY - timedelta(days=index % 365)).isoformat(),
            subject=("Matematik", "Türkçe", "Fizik", "Kimya")[index % 4],
            correct=20 + index % 30, incorrect=5 + index % 10, blank=3 + index % 6,
        ) for index in range(exam_count)]
        questions = []
        expected = {}
        for index in range(count):
            exam = exams[index % exam_count]
            size = exam.correct + exam.incorrect + exam.blank
            order = rng.randint(1, size)
            stage = ("early", "middle", "late")[min(2, ((order - 1) * 3) // size)]
            key = (getattr(exam, "exam_type", "branch"), exam.subject)
            expected[key] = expected.get(key, 0) + 1
            questions.append(Question(
                id=f"q-{index}", exam_id=exam.id, question_number=rng.randint(1, size),
                solve_order=order, time_spent_seconds=rng.randint(15, 240),
                subject=exam.subject, topic=f"Topic {rng.randrange(60):02d}",
            ))
        with tempfile.TemporaryDirectory(prefix="hamartia-order-bench-") as directory:
            storage = StorageService(Path(directory))
            storage.save_list("exams.json", exams)
            storage.save_list("questions.json", questions)
            def summarize():
                saved_questions = storage.load_list("questions.json", Question)
                saved_exams = storage.load_list("exams.json", Exam)
                return topic_priorities(saved_questions, today=TODAY, exams=saved_exams)["question_order"]
            summary = summarize()
            actual = {
                (row["exam_type"], row["subject"]): sum(row[stage]["wrong_count"] for stage in ("early", "middle", "late"))
                for row in summary
            }
            assert actual == expected
            results.append({
                "questions": count, "exams": exam_count,
                "persisted_bytes": (storage.data_dir / "questions.json").stat().st_size,
                "warm_full_summary": measure(summarize, repeats),
                "correctness": "stage counts match independent seeded oracle",
            })
    emit({"benchmark": "question_order_summary", "seed": SEED, "runs": results}, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    if not 3 <= args.repeats <= 31:
        parser.error("--repeats must be between 3 and 31")
    run(repeats=args.repeats, json_output=args.json_output)
