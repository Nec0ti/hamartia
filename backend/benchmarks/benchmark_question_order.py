"""Measure solve-order summaries over seeded, persisted multi-exam mistakes."""

import argparse
import random
from collections import Counter, defaultdict
import tempfile
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, measure, probe_detects_mutation

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
                fixed_positions = [1, 40, 41, 80, 81, size]
                remaining = [value for value in range(1, size + 1) if value not in fixed_positions]
                positions[exam_index] = (
                    iter(fixed_positions + rng.sample(remaining, exam.incorrect - len(fixed_positions))),
                    iter([1, 40, 41, 80, 81, size] + rng.sample(remaining, exam.incorrect - len(fixed_positions))),
                )
            question_number = next(positions[exam_index][0])
            order = next(positions[exam_index][1])
            stage = "early" if order <= 40 else "middle" if order <= 80 else "late"
            key = (getattr(exam, "exam_type", "branch"), exam.subject)
            time_spent = None if index % 97 == 0 else 15 + index % 226
            expected[key][stage].append(time_spent)
            questions.append(Question(
                id=f"q-{index}", exam_id=exam.id, question_number=question_number,
                solve_order=order, time_spent_seconds=time_spent,
                subject=exam.subject, topic=f"Topic {rng.randrange(60):02d}",
            ))
        sectioned_exam = Exam(
            id="boundary-tyt", date=TODAY.isoformat(), exam_type="tyt", subject="TYT Geneli",
            correct=85, incorrect=22, blank=13,
            sections=[
                {"subject": "Türkçe", "correct": 30, "incorrect": 7, "blank": 3},
                {"subject": "Matematik", "correct": 27, "incorrect": 8, "blank": 5},
                {"subject": "Fen", "correct": 13, "incorrect": 4, "blank": 3},
                {"subject": "Sosyal", "correct": 15, "incorrect": 3, "blank": 2},
            ],
        )
        exams.append(sectioned_exam)
        section_counts = {"Türkçe": (30, 7, 3), "Matematik": (27, 8, 5),
                          "Fen": (13, 4, 3), "Sosyal": (15, 3, 2)}
        for subject, (correct, incorrect, blank) in section_counts.items():
            section_size = correct + incorrect + blank
            key = ("tyt", subject)
            expected[key]["early"].append(1)
            expected[key]["late"].append(3600)
            questions.extend((
                Question(id=f"boundary-{subject}-first", exam_id=sectioned_exam.id,
                         question_number=1, solve_order=1, time_spent_seconds=1,
                         subject=subject, exam_section_total=section_size),
                Question(id=f"boundary-{subject}-last", exam_id=sectioned_exam.id,
                         question_number=section_size, solve_order=section_size, time_spent_seconds=3600,
                         subject=subject, exam_section_total=section_size),
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
            expected_rows = []
            group_exam_counts = Counter((exam.exam_type, section.subject) for exam in exams for section in exam.sections)
            group_exam_counts.update(Counter((exam.exam_type, exam.subject) for exam in exams if not exam.sections))
            for key, stages in expected.items():
                row = {"exam_type": key[0], "subject": key[1], "exam_count": group_exam_counts[key]}
                for stage, times in stages.items():
                    valid_times = [value for value in times if value is not None]
                    row[stage] = {
                        "wrong_count": len(times),
                        "median_seconds": median(valid_times) if valid_times else None,
                    }
                expected_rows.append(row)
            expected_rows.sort(key=lambda row: (-sum(row[stage]["wrong_count"] for stage in ("early", "middle", "late")),
                                                row["subject"].casefold(), row["exam_type"]))
            assert_oracle(summary, expected_rows, "question-order full summary")
            assert len({(item.exam_id, item.subject if item.exam_section_total else "", item.question_number) for item in questions}) == len(questions)
            assert len({(item.exam_id, item.subject if item.exam_section_total else "", item.solve_order) for item in questions}) == len(questions)
            size = exams[0].correct + exams[0].incorrect + exams[0].blank
            invalid = [
                Question(id="unknown-exam", exam_id="missing", question_number=1, solve_order=1, time_spent_seconds=30),
                Question(id="missing-order", exam_id=exams[0].id, question_number=1, solve_order=None),
                Question(id="out-of-range", exam_id=exams[0].id, question_number=size + 1,
                         solve_order=size + 1, time_spent_seconds=30),
            ]
            assert_oracle(topic_priorities(questions + invalid, today=TODAY, exams=exams)["question_order"],
                          expected_rows, "invalid question-order references excluded")
            mutation_probes = [probe_detects_mutation(
                summary, expected_rows,
                lambda rows: rows[0]["early"].__setitem__("median_seconds", -1),
                "question-order median corrupted",
            )]
            results.append({
                "questions": len(questions), "exams": len(exams),
                "persisted_bytes": (storage.data_dir / "questions.json").stat().st_size,
                "warm_full_summary": measure(summarize, repeats),
                "correctness": "unique in-range positions and each stage count/median match oracle; unknown, missing-order, and out-of-range references are excluded",
                "mutation_probes": mutation_probes,
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
