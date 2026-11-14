"""Seeded persisted-data benchmark for non-AI study flows."""

import argparse
import json
import random
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from app.core.practice import practice_topic_summaries
from app.core.progression import progression_summary
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, PracticeSession, Question, ReviewAttempt
from app.services.storage import StorageService
from benchmark_common import emit

SEED = 20261114
TODAY = date(2026, 11, 14)


def percentile(samples, percent):
    ordered = sorted(samples)
    return ordered[max(0, (len(ordered) * percent + 99) // 100 - 1)]


def measure(operation, repeats):
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - started)
    return {"samples": len(samples), "p50_seconds": round(median(samples), 6),
            "p95_seconds": round(percentile(samples, 95), 6)}


def fixtures(exam_count, question_count, session_count):
    rng = random.Random(SEED)
    exams = []
    for index in range(exam_count):
        sectioned = index % 10 == 0
        sections = [{"subject": subject, "correct": 10 + index % 10,
                     "incorrect": 1 + index % 4, "blank": index % 3}
                    for subject in ("Türkçe", "Matematik", "Fen", "Sosyal")] if sectioned else []
        exams.append(Exam(
            id=f"exam-{index}", date=(TODAY - timedelta(days=index % 730)).isoformat(),
            exam_type="tyt" if sectioned else "branch",
            subject="TYT Geneli" if sectioned else rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")),
            correct=sum(section["correct"] for section in sections) if sectioned else 20 + index % 30,
            incorrect=sum(section["incorrect"] for section in sections) if sectioned else 2 + index % 8,
            blank=sum(section["blank"] for section in sections) if sectioned else index % 6,
            duration_minutes=35 + index % 80, sections=sections,
        ))
    questions = [Question(
        id=f"question-{index}", exam_id=f"exam-{index % exam_count}",
        question_number=index % 40 + 1, solve_order=index % 40 + 1,
        time_spent_seconds=15 + index % 150,
        subject=rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")),
        topic=f"Konu {index % 40:02d}", ocr_text=f"Seeded question text {index:05d} " + "açıklama " * 12,
        created_at=(TODAY - timedelta(days=index % 365)).isoformat() + "T12:00:00Z",
        hamartia_tag=rng.choice(("[Knowledge Gap]", "[Reading Slip]", "[Distractor Trap]")),
        review_attempts=[ReviewAttempt(
            attempted_at=(TODAY - timedelta(days=(index + offset) % 45)).isoformat() + "T09:00:00Z",
            correct=(index + offset) % 3 != 0,
        ) for offset in range(index % 4)],
    ) for index in range(question_count)]
    sessions = [PracticeSession(
        id=f"session-{index}", date=(TODAY - timedelta(days=index % 730)).isoformat(),
        subject=rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")), topic=f"Konu {index % 80:02d}",
        correct=index % 26, incorrect=index % 8, blank=1 + index % 5,
        duration_minutes=10 + index % 60, duration_seconds=index % 60,
    ) for index in range(session_count)]
    return exams, questions, sessions


def run(exam_count=1500, question_count=2500, session_count=4000, repeats=21, json_output=None):
    if min(exam_count, question_count, session_count) < 1 or max(exam_count, question_count, session_count) > 10_000:
        raise ValueError("record counts must be between 1 and 10,000")
    if not 5 <= repeats <= 101:
        raise ValueError("repeats must be between 5 and 101")

    exams, questions, sessions = fixtures(exam_count, question_count, session_count)
    with tempfile.TemporaryDirectory(prefix="hamartia-bench-") as directory:
        root = Path(directory)
        storage = StorageService(root)
        storage.save_list("exams.json", exams)
        storage.save_list("questions.json", questions)
        storage.save_list("practice_sessions.json", sessions)
        persisted_bytes = {name: (root / name).stat().st_size for name in (
            "exams.json", "questions.json", "practice_sessions.json")}

        # First access through a fresh service, followed by warmed in-process reads.
        cold = {}
        for name, model, expected in (("exams.json", Exam, exam_count),
                                      ("questions.json", Question, question_count),
                                      ("practice_sessions.json", PracticeSession, session_count)):
            fresh = StorageService(root)
            started = time.perf_counter()
            loaded = fresh.load_list(name, model)
            cold[name] = round(time.perf_counter() - started, 6)
            assert len(loaded) == expected
        warm = {
            name: measure(lambda n=name, m=model, c=count: _assert_count(storage, n, m, c), repeats)
            for name, model, count in (("exams.json", Exam, exam_count),
                                       ("questions.json", Question, question_count),
                                       ("practice_sessions.json", PracticeSession, session_count))
        }

        assert len(progression_summary(storage.load_list("exams.json", Exam), today=TODAY)["last_active_date"]) == 10
        progression = measure(lambda: progression_summary(storage.load_list("exams.json", Exam), today=TODAY), repeats)
        priorities = measure(lambda: topic_priorities(
            storage.load_list("questions.json", Question), today=TODAY,
            exams=storage.load_list("exams.json", Exam)), repeats)
        summaries = measure(lambda: practice_topic_summaries(
            storage.load_list("practice_sessions.json", PracticeSession)), repeats)
        assert sum(group["session_count"] for group in practice_topic_summaries(sessions)) == session_count

        update_ids = [f"question-{index}" for index in range(question_count - 10, question_count)]
        update = measure(lambda: _update_question(storage, update_ids.pop(), "[Reading Slip]"), 10)
        assert all(q.hamartia_tag == "[Reading Slip]" for q in storage.load_list("questions.json", Question)[-10:])

        delete_ids = [f"question-{index}" for index in range(question_count - 20, question_count - 10)]
        delete = measure(lambda: _delete_question(storage, delete_ids.pop()), 10)
        remaining = storage.load_list("questions.json", Question)
        assert len(remaining) == question_count - 10
        assert not any(q.id in {f"question-{i}" for i in range(question_count - 20, question_count - 10)} for q in remaining)

        concurrent = [Exam(
            id=f"concurrent-{i}", date=TODAY.isoformat(), subject="Matematik", correct=1, incorrect=0, blank=0,
        ) for i in range(16)]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item: storage.append_list("exams.json", item, Exam), concurrent))
        concurrent_seconds = time.perf_counter() - started
        final_exams = storage.load_list("exams.json", Exam)
        assert len(final_exams) == exam_count + len(concurrent)
        assert {item.id for item in final_exams if item.id.startswith("concurrent-")} == {item.id for item in concurrent}

        emit({
            "benchmark": "persisted_mixed_study_workloads", "seed": SEED,
            "records": {"exams": exam_count, "questions": question_count, "practice_sessions": session_count},
            "persisted_json_bytes": persisted_bytes,
            "first_service_load_seconds": cold, "warm_load": warm,
            "progression_full_history": progression, "question_insights_full_history": priorities,
            "practice_summaries_full_history": summaries,
            "question_update_10_records": update, "question_delete_10_records": delete,
            "concurrent_appends": {"workers": 4, "records": len(concurrent), "seconds": round(concurrent_seconds, 6)},
            "correctness": "all assertions passed",
        }, json_output)


def _assert_count(storage, name, model, count):
    assert len(storage.load_list(name, model)) == count


def _update_question(storage, question_id, tag):
    def update(items):
        for item in items:
            if item.id == question_id:
                item.hamartia_tag = tag
                return True
        return False
    assert storage.update_list("questions.json", Question, update)


def _delete_question(storage, question_id):
    def delete(items):
        for index, item in enumerate(items):
            if item.id == question_id:
                items.pop(index)
                return True
        return False
    assert storage.update_list("questions.json", Question, delete)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exams", type=int, default=1500)
    parser.add_argument("--questions", type=int, default=2500)
    parser.add_argument("--sessions", type=int, default=4000)
    parser.add_argument("--repeats", type=int, default=21)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    run(args.exams, args.questions, args.sessions, args.repeats, args.json_output)
