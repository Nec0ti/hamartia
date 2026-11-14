"""Seeded persisted-data benchmark for non-AI study flows."""

import argparse
import json
import random
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from collections import Counter, defaultdict
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
    operation()
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
        sections = [
            {"subject": "Türkçe", "correct": 30, "incorrect": 7, "blank": 3},
            {"subject": "Matematik", "correct": 27, "incorrect": 8, "blank": 5},
            {"subject": "Fen", "correct": 13, "incorrect": 4, "blank": 3},
            {"subject": "Sosyal", "correct": 15, "incorrect": 3, "blank": 2},
        ] if sectioned else []
        exams.append(Exam(
            id=f"exam-{index}", date=(TODAY - timedelta(days=index % 730)).isoformat(),
            exam_type="tyt" if sectioned else "branch",
            subject="TYT Geneli" if sectioned else rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")),
            correct=sum(section["correct"] for section in sections) if sectioned else 40,
            incorrect=sum(section["incorrect"] for section in sections) if sectioned else 30,
            blank=sum(section["blank"] for section in sections) if sectioned else 20,
            duration_minutes=35 + index % 80, sections=sections,
        ))
    assignments = []
    grouped = defaultdict(list)
    for index in range(question_count):
        exam_index = index % exam_count
        exam = exams[exam_index]
        section_index = (index // exam_count) % len(exam.sections) if exam.sections else None
        assignments.append((exam_index, section_index))
        grouped[(exam_index, section_index)].append(index)
    positions = {}
    for key, indices in grouped.items():
        exam_index, section_index = key
        exam = exams[exam_index]
        if section_index is None:
            total, errors = exam.correct + exam.incorrect + exam.blank, exam.incorrect
        else:
            section = exam.sections[section_index]
            total, errors = section.correct + section.incorrect + section.blank, section.incorrect
        assert len(indices) <= errors
        positions[key] = (
            iter(rng.sample(range(1, total + 1), len(indices))),
            iter(rng.sample(range(1, total + 1), len(indices))),
        )
    questions = []
    for index, (exam_index, section_index) in enumerate(assignments):
        exam = exams[exam_index]
        question_number = next(positions[(exam_index, section_index)][0])
        solve_order = next(positions[(exam_index, section_index)][1])
        section = exam.sections[section_index] if section_index is not None else None
        attempt_count = index % 4
        last_age = 1 + index % 30
        all_correct = index % 3 == 0
        questions.append(Question(
            id=f"question-{index}", exam_id=exam.id,
            question_number=question_number, solve_order=solve_order,
            time_spent_seconds=15 + index % 150,
            subject=section.subject if section else exam.subject,
            topic=f"Konu {index % 40:02d}", ocr_text=f"Seeded question text {index:05d} " + "açıklama " * 12,
            created_at=(TODAY - timedelta(days=index % 365)).isoformat() + "T12:00:00Z",
            hamartia_tag=rng.choice(("[Knowledge Gap]", "[Reading Slip]", "[Distractor Trap]")),
            exam_section_total=(section.correct + section.incorrect + section.blank) if section else None,
            review_attempts=[ReviewAttempt(
                attempted_at=(TODAY - timedelta(days=last_age + attempt_count - offset - 1)).isoformat() + "T09:00:00Z",
                correct=all_correct if all_correct else offset < attempt_count - 1,
            ) for offset in range(attempt_count)],
        ))
    sessions = [PracticeSession(
        id=f"session-{index}", date=(TODAY - timedelta(days=index % 730)).isoformat(),
        subject=rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")), topic=f"Konu {index % 80:02d}",
        correct=index % 26, incorrect=index % 8, blank=1 + index % 5,
        duration_minutes=10 + index % 60, duration_seconds=index % 60,
    ) for index in range(session_count)]
    return exams, questions, sessions


def run(exam_count=1500, question_count=2500, session_count=4000, repeats=21, json_output=None):
    if min(exam_count, session_count) < 1 or not 21 <= question_count <= 10_000 or max(exam_count, session_count) > 10_000:
        raise ValueError("record counts must be between 1 and 10,000")
    if question_count > exam_count * 12:
        raise ValueError("question count must fit each exam/section's incorrect-answer capacity")
    if not 5 <= repeats <= 101:
        raise ValueError("repeats must be between 5 and 101")

    exams, questions, sessions = fixtures(exam_count, question_count, session_count)
    _assert_valid_questions(questions, exams)
    with tempfile.TemporaryDirectory(prefix="hamartia-bench-") as directory:
        root = Path(directory)
        storage = StorageService(root)
        storage.save_list("exams.json", exams)
        storage.save_list("questions.json", questions)
        storage.save_list("practice_sessions.json", sessions)
        persisted_bytes = {name: (root / name).stat().st_size for name in (
            "exams.json", "questions.json", "practice_sessions.json")}

        # First access through a fresh service, followed by warmed in-process reads.
        first_service_load = {}
        for name, model, expected in (("exams.json", Exam, exam_count),
                                      ("questions.json", Question, question_count),
                                      ("practice_sessions.json", PracticeSession, session_count)):
            fresh = StorageService(root)
            started = time.perf_counter()
            loaded = fresh.load_list(name, model)
            first_service_load[name] = round(time.perf_counter() - started, 6)
            assert len(loaded) == expected
        warm = {
            name: measure(lambda n=name, m=model, c=count: _assert_count(storage, n, m, c), repeats)
            for name, model, count in (("exams.json", Exam, exam_count),
                                       ("questions.json", Question, question_count),
                                       ("practice_sessions.json", PracticeSession, session_count))
        }

        progression_result = progression_summary(storage.load_list("exams.json", Exam), today=TODAY)
        assert progression_result == _expected_progression(exams)
        progression = measure(lambda: _assert_equal(
            progression_summary(storage.load_list("exams.json", Exam), today=TODAY), _expected_progression(exams)), repeats)
        priority_result = topic_priorities(
            storage.load_list("questions.json", Question), today=TODAY,
            exams=storage.load_list("exams.json", Exam))
        expected_priorities = _expected_priorities(questions, exams)
        assert priority_result == expected_priorities
        assert priority_result["pending_questions"] > 0 and priority_result["scheduled_questions"] > 0
        priorities = measure(lambda: _assert_equal(topic_priorities(
            storage.load_list("questions.json", Question), today=TODAY,
            exams=storage.load_list("exams.json", Exam)), expected_priorities), repeats)
        expected_practice = _expected_practice(sessions)
        assert practice_topic_summaries(sessions) == expected_practice
        summaries = measure(lambda: _assert_equal(practice_topic_summaries(
            storage.load_list("practice_sessions.json", PracticeSession)), expected_practice), repeats)

        update_ids = [f"question-{index}" for index in range(question_count - 11, question_count)]
        update = measure(lambda: _update_question(storage, update_ids.pop(), "[Reading Slip]"), 10)
        assert all(q.hamartia_tag == "[Reading Slip]" for q in storage.load_list("questions.json", Question)[-11:])

        delete_ids = [f"question-{index}" for index in range(question_count - 22, question_count - 11)]
        delete = measure(lambda: _delete_question(storage, delete_ids.pop()), 10)
        remaining = storage.load_list("questions.json", Question)
        assert len(remaining) == question_count - 11
        assert not any(q.id in {f"question-{i}" for i in range(question_count - 22, question_count - 11)} for q in remaining)

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
            "first_service_load_seconds": first_service_load, "warm_load": warm,
            "progression_full_history": progression, "question_insights_full_history": priorities,
            "practice_summaries_full_history": summaries,
            "question_update_10_records": update, "question_delete_10_records": delete,
            "concurrent_appends": {"workers": 4, "records": len(concurrent), "seconds": round(concurrent_seconds, 6)},
            "correctness": "progression, topic/review/order insights, practice groups/trends, mutation targets, and all appended IDs match independent oracles",
        }, json_output)


def _assert_equal(actual, expected):
    assert actual == expected


def _assert_valid_questions(questions, exams):
    exam_by_id = {exam.id: exam for exam in exams}
    positions = set()
    for question in questions:
        exam = exam_by_id[question.exam_id]
        if question.exam_section_total:
            section = next(section for section in exam.sections if section.subject == question.subject)
            total = section.correct + section.incorrect + section.blank
            assert question.exam_section_total == total
            assert question.question_number <= total
            scope = (exam.id, section.subject)
        else:
            total = exam.correct + exam.incorrect + exam.blank
            assert question.subject == exam.subject
            assert question.question_number <= total
            scope = (exam.id, "")
        assert 1 <= question.solve_order <= total
        assert (*scope, question.question_number) not in positions
        assert (*scope, "order", question.solve_order) not in positions
        positions.add((*scope, question.question_number))
        positions.add((*scope, "order", question.solve_order))


def _expected_progression(exams):
    xp = 0
    dates = set()
    for exam in exams:
        net = exam.correct - exam.incorrect / 4
        duration = exam.duration_minutes or 1
        xp += max(0, int(net * exam.correct * 1.5 - duration * exam.incorrect * 0.25))
        dates.add(date.fromisoformat(exam.date))
    last = max(day for day in dates if day <= TODAY)
    streak = 0
    while last - timedelta(days=streak) in dates:
        streak += 1
    return {"total_xp": xp, "level": xp // 500 + 1 if xp >= 500 else 1,
            "streak_days": streak, "last_active_date": last.isoformat()}


def _expected_priorities(questions, exams):
    exam_by_id = {exam.id: exam for exam in exams}
    topic_groups = {}
    order_groups = {}
    reviews = []
    today_ids, today_correct, today_incorrect = set(), 0, 0
    pending = scheduled = unclassified = 0
    intervals = (1, 3, 7, 14, 30)
    for question in questions:
        for attempt in question.review_attempts:
            day = datetime.fromisoformat(attempt.attempted_at.replace("Z", "+00:00")).date()
            if day == TODAY:
                today_ids.add(question.id)
                today_correct += int(attempt.correct)
                today_incorrect += int(not attempt.correct)

        if question.review_attempts:
            attempts = question.review_attempts
            last_day = datetime.fromisoformat(attempts[-1].attempted_at.replace("Z", "+00:00")).date()
            streak = 0
            for attempt in reversed(attempts):
                if not attempt.correct:
                    break
                streak += 1
            interval = intervals[min(streak - 1, len(intervals) - 1)] if streak else 1
            due_day = last_day + timedelta(days=interval)
            last_correct = attempts[-1].correct
        else:
            streak, due_day, last_correct = 0, TODAY, None
        due = due_day <= TODAY
        subject = question.subject.strip() or "Ders belirtilmedi"
        topic = question.topic.strip() or "Konu belirtilmedi"
        exam = exam_by_id.get(question.exam_id)
        size = question.exam_section_total or exam.correct + exam.incorrect + exam.blank
        order_subject = question.subject if question.exam_section_total else exam.subject
        stage = ("early", "middle", "late")[min(2, ((question.solve_order - 1) * 3) // size)]
        key = (exam.exam_type, order_subject)
        order = order_groups.setdefault(key, {"exam_ids": set(), **{name: [] for name in ("early", "middle", "late")}})
        order["exam_ids"].add(exam.id)
        order[stage].append(question.time_spent_seconds)
        if not due:
            scheduled += bool(due_day)
            continue
        pending += 1
        unclassified += not question.subject.strip() or not question.topic.strip()
        topic_key = (subject.casefold(), topic.casefold())
        group = topic_groups.setdefault(topic_key, {
            "subject": subject, "topic": topic, "pending_count": 0,
            "last_seen": "", "tags": Counter(),
        })
        group["pending_count"] += 1
        group["last_seen"] = max(group["last_seen"], question.created_at[:10])
        group["tags"][question.hamartia_tag] += 1
        reviews.append({
            "id": question.id, "subject": subject, "topic": topic,
            "hamartia_tag": question.hamartia_tag, "ocr_text": question.ocr_text,
            "has_image": bool(question.image_path), "due_date": due_day.isoformat(),
            "due": due, "streak": streak, "last_correct": last_correct,
        })

    topics = [{**group, "tags": dict(group["tags"])} for group in topic_groups.values()]
    topics.sort(key=lambda group: (-group["pending_count"], group["subject"].casefold(), group["topic"].casefold()))
    reviews.sort(key=lambda item: (item["due_date"], item["subject"].casefold(), item["topic"].casefold(), item["id"]))
    order_rows = []
    for (exam_type, subject), group in order_groups.items():
        row = {"exam_type": exam_type, "subject": subject, "exam_count": len(group["exam_ids"])}
        for stage in ("early", "middle", "late"):
            values = group[stage]
            row[stage] = {"wrong_count": len(values), "median_seconds": median(values) if values else None}
        order_rows.append(row)
    order_rows.sort(key=lambda row: (-sum(row[stage]["wrong_count"] for stage in ("early", "middle", "late")),
                                    row["subject"].casefold(), row["exam_type"]))
    return {
        "total_questions": len(questions), "pending_questions": pending,
        "scheduled_questions": scheduled, "unclassified_questions": unclassified,
        "today_questions": len(today_ids), "today_correct": today_correct,
        "today_incorrect": today_incorrect, "question_order": order_rows,
        "topics": topics, "reviews": reviews,
    }


def _expected_practice(sessions):
    groups = {}
    for session in sessions:
        key = (session.subject.casefold(), session.topic.casefold())
        group = groups.setdefault(key, {
            "subject": session.subject, "topic": session.topic, "sessions": [],
            "correct": 0, "incorrect": 0, "blank": 0,
        })
        group["sessions"].append(session)
        for field in ("correct", "incorrect", "blank"):
            group[field] += getattr(session, field)
    result = []
    for group in groups.values():
        ordered = sorted(group.pop("sessions"), key=lambda item: (item.date, item.created_at, item.id))
        answered = group["correct"] + group["incorrect"]
        group.update({
            "session_count": len(ordered), "answered": answered,
            "net": sum(item.correct - item.incorrect / 4 for item in ordered),
            "accuracy": group["correct"] / answered if answered else None,
            "trend": [{
                "id": item.id, "date": item.date,
                "net": item.correct - item.incorrect / 4,
                "accuracy": item.correct / (item.correct + item.incorrect) if item.correct + item.incorrect else None,
            } for item in ordered],
        })
        result.append(group)
    result.sort(key=lambda item: (item["subject"].casefold(), item["topic"].casefold()))
    return result


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
