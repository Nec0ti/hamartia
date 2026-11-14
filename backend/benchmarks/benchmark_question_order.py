"""Measure solve-order summaries over seeded, persisted multi-exam mistakes."""

import argparse
import random
from collections import defaultdict
import tempfile
from datetime import date, timedelta
from pathlib import Path
from statistics import median

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
        exam_count = count // 20
        exams = [Exam(
            id=f"exam-{index}", date=(TODAY - timedelta(days=index % 365)).isoformat(),
            subject=("Matematik", "Türkçe", "Fizik", "Kimya")[index % 4],
            correct=80, incorrect=20, blank=20,
        ) for index in range(exam_count)]
        questions = []
        expected = defaultdict(lambda: {stage: [] for stage in ("early", "middle", "late")})
        positions = {}
        for index in range(count):
            exam_index = index % exam_count
            exam = exams[exam_index]
            size = exam.correct + exam.incorrect + exam.blank
            if exam_index not in positions:
                positions[exam_index] = (
                    iter(rng.sample(range(1, size + 1), exam.incorrect)),
                    iter(rng.sample(range(1, size + 1), exam.incorrect)),
                )
            question_number = next(positions[exam_index][0])
            order = next(positions[exam_index][1])
            stage = ("early", "middle", "late")[min(2, ((order - 1) * 3) // size)]
            key = (getattr(exam, "exam_type", "branch"), exam.subject)
            time_spent = 15 + index % 226
            expected[key][stage].append(time_spent)
            questions.append(Question(
                id=f"q-{index}", exam_id=exam.id, question_number=question_number,
                solve_order=order, time_spent_seconds=time_spent,
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
            actual = {(row["exam_type"], row["subject"]): row for row in summary}
            assert set(actual) == set(expected)
            for key, stages in expected.items():
                for stage, times in stages.items():
                    assert actual[key][stage] == {
                        "wrong_count": len(times),
                        "median_seconds": median(times) if times else None,
                    }
            assert len({(item.exam_id, item.question_number) for item in questions}) == count
            assert len({(item.exam_id, item.solve_order) for item in questions}) == count
            size = exams[0].correct + exams[0].incorrect + exams[0].blank
            invalid = [
                Question(id="unknown-exam", exam_id="missing", question_number=1, solve_order=1, time_spent_seconds=30),
                Question(id="missing-order", exam_id=exams[0].id, question_number=1, solve_order=None),
                Question(id="out-of-range", exam_id=exams[0].id, question_number=size + 1,
                         solve_order=size + 1, time_spent_seconds=30),
            ]
            assert topic_priorities(questions + invalid, today=TODAY, exams=exams)["question_order"] == summary
            results.append({
                "questions": count, "exams": exam_count,
                "persisted_bytes": (storage.data_dir / "questions.json").stat().st_size,
                "warm_full_summary": measure(summarize, repeats),
                "correctness": "unique in-range positions and each stage count/median match oracle; unknown, missing-order, and out-of-range references are excluded",
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
