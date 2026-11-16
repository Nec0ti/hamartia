"""Seeded persisted-data benchmark for non-AI study flows."""

import argparse
import json
import random
import tempfile
import time
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from app.core.practice import practice_topic_summaries
from app.core.progression import progression_summary
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, ExamScoringProfile, PracticeSession, Question, ReviewAttempt
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, probe_oracle_self_check, seeded_photo_png

SEED = 20261114
TODAY = date(2026, 11, 14)
PRACTICE_PROFILE_FIXTURES = {
    ("benchmark-mixed", 1): {
        "profile_id": "benchmark-mixed", "version": 1,
        "display_name": "Mixed workload v1", "country_label": "Fixture",
        "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
    },
    ("benchmark-mixed", 2): {
        "profile_id": "benchmark-mixed", "version": 2,
        "display_name": "Mixed workload v2", "country_label": "Fixture",
        "scoring_rule": {"correct_points": "3/2", "wrong_penalty": "1/3", "blank_points": "1/5"},
    },
    ("legacy-yks", 1): {
        "profile_id": "legacy-yks", "version": 1,
        "display_name": "YKS (legacy)", "country_label": "Türkiye",
        "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
    },
}


def _practice_profile(index):
    key = (("benchmark-mixed", 1), ("benchmark-mixed", 2), ("legacy-yks", 1))[index % 3]
    return ExamScoringProfile(**PRACTICE_PROFILE_FIXTURES[key])


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
    subjects = ("Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji", "Tarih", "Coğrafya", "Felsefe")
    topics = ("Konu 00",) * 12 + ("Konu 01",) * 8 + ("Konu 02",) * 5 + tuple(f"Konu {i:02d}" for i in range(3, 40))
    exams = []
    for index in range(exam_count):
        sectioned = index % 10 == 0
        sections = [
            {"subject": "Türkçe", "correct": 30, "incorrect": 7, "blank": 3},
            {"subject": "Matematik", "correct": 27, "incorrect": 8, "blank": 5},
            {"subject": "Fen", "correct": 13, "incorrect": 4, "blank": 3},
            {"subject": "Sosyal", "correct": 15, "incorrect": 3, "blank": 2},
        ] if sectioned else []
        age = 0 if index == 0 else 1 if index == 1 else min(730, int(rng.expovariate(1 / 120)))
        exams.append(Exam(
            id=f"exam-{index}", date=(TODAY - timedelta(days=age)).isoformat(),
            exam_type="tyt" if sectioned else "branch",
            subject="TYT Geneli" if sectioned else rng.choices(
                ("Matematik", "Türkçe", "Fizik", "Kimya"), weights=(45, 30, 15, 10), k=1)[0],
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
    image_count = max(1, min(64, round(question_count * 0.04)))
    image_indices = {round(index * (question_count - 1) / max(1, image_count - 1))
                     for index in range(image_count)}
    image_files = {}
    questions = []
    for index, (exam_index, section_index) in enumerate(assignments):
        exam = exams[exam_index]
        question_number = next(positions[(exam_index, section_index)][0])
        solve_order = next(positions[(exam_index, section_index)][1])
        section = exam.sections[section_index] if section_index is not None else None
        attempt_count = rng.choices((0, 1, 2, 3, 6), weights=(45, 25, 17, 10, 3), k=1)[0]
        last_age = 0 if index % 8 == 1 else 1 + index % 30
        all_correct = index % 3 == 1
        reviewed_at = TODAY.isoformat() if index == 0 else ""
        reference = None
        if index == question_count - 1:
            reference = {
                "framework": "Synthetic framework B", "source": "Benchmark fixture B",
                "version": "v2", "grade_year": "Year 2", "unit_theme": "Made-up unit B",
                "learning_outcome": "Explain invented pattern B", "process_component": "Reasoning B",
            }
        elif index == question_count - 2:
            reference = {
                "framework": "Synthetic framework A", "source": "Benchmark fixture A",
                "version": "v1", "grade_year": "Year 1", "unit_theme": "Made-up unit A",
                "learning_outcome": "Explain invented pattern A", "process_component": "Reasoning A",
            }
        elif index == question_count - 3:
            reference = {
                "framework": "Synthetic framework C", "source": "Benchmark fixture C",
                "version": "v3", "grade_year": "Year 3", "unit_theme": "Made-up unit C",
                "learning_outcome": "Explain invented pattern C", "process_component": "Reasoning C",
            }
        review_attempts = [ReviewAttempt(
            attempted_at=(TODAY - timedelta(days=last_age + attempt_count - offset - 1)).isoformat() + "T09:00:00Z",
            attempt_day=(TODAY - timedelta(days=last_age + attempt_count - offset - 1)).isoformat(),
            correct=all_correct if all_correct else offset < attempt_count - 1,
        ) for offset in range(attempt_count)]
        if review_attempts and index % 13 == 0:
            review_attempts[-1].attempt_day = ""  # legacy UTC date fallback
        subject = "" if index == 3 else section.subject if section else exam.subject
        topic = "" if index == 3 else rng.choice(topics)
        image_name = ""
        image_path = ""
        if index in image_indices:
            width, height = ((320, 240), (640, 480), (1024, 768))[index % 3]
            image_name = f"q_{index:05d}.png"
            image_path = f"uploads/{image_name}"
            image_files[image_name] = seeded_photo_png(width, height, rng)
        length_class = index % 20
        if length_class < 11:
            ocr_text = f"Question {index}: identify the correct result."
        elif length_class < 18:
            ocr_text = f"Question {index}: " + ("Given the conditions and the diagram, explain the reasoning. " * 8)
        else:
            ocr_text = f"Question {index}: " + ("Extended passage and multi-step context. " * 48)
        questions.append(Question(
            id=f"question-{index}", exam_id=exam.id,
            question_number=question_number, solve_order=solve_order,
            time_spent_seconds=15 + index % 150,
            subject=subject,
            topic=topic, ocr_text=ocr_text,
            image_name=image_name, image_path=image_path,
            reviewed_at=reviewed_at,
            created_at=(TODAY - timedelta(days=index % 365)).isoformat() + "T12:00:00Z",
            hamartia_tag=rng.choice(("[Knowledge Gap]", "[Reading Slip]", "[Distractor Trap]")),
            exam_section_total=(section.correct + section.incorrect + section.blank) if section else None,
            review_attempts=review_attempts,
            curriculum_reference=reference or {},
        ))
    sessions = [PracticeSession(
        id=f"session-{index}", date=(TODAY - timedelta(days=min(730, int(rng.expovariate(1 / 120))))).isoformat(),
        subject=rng.choices(subjects, weights=(34, 22, 12, 10, 8, 6, 5, 3), k=1)[0],
        topic=rng.choice(topics),
        correct=index % 26, incorrect=index % 8, blank=1 + index % 5,
        duration_minutes=10 + index % 60, duration_seconds=index % 60,
        scoring_profile=_practice_profile(index),
    ) for index in range(session_count)]
    sessions[0] = PracticeSession(
        id="session-0", date=TODAY.isoformat(), subject=" Matematik ", topic=" Boundary ",
        correct=0, incorrect=0, blank=6, duration_minutes=0, duration_seconds=59,
        scoring_profile=_practice_profile(0),
    )
    sessions[1] = PracticeSession(
        id="session-1", date=(TODAY - timedelta(days=729)).isoformat(), subject="matematik", topic="boundary",
        correct=1000, incorrect=4, blank=0, duration_minutes=90, duration_seconds=0,
        scoring_profile=_practice_profile(1),
    )
    return exams, questions, sessions, image_files


def run(exam_count=1500, question_count=2500, session_count=4000, repeats=21, json_output=None):
    if min(exam_count, session_count) < 1 or not 21 <= question_count <= 10_000 or max(exam_count, session_count) > 10_000:
        raise ValueError("record counts must be between 1 and 10,000")
    if question_count > exam_count * 12:
        raise ValueError("question count must fit each exam/section's incorrect-answer capacity")
    if not 5 <= repeats <= 101:
        raise ValueError("repeats must be between 5 and 101")

    exams, questions, sessions, image_files = fixtures(exam_count, question_count, session_count)
    _assert_valid_questions(questions, exams)
    with tempfile.TemporaryDirectory(prefix="hamartia-bench-") as directory:
        root = Path(directory)
        storage = StorageService(root)
        uploads = root / "uploads"
        uploads.mkdir()
        for name, contents in image_files.items():
            (uploads / name).write_bytes(contents)
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
            name: measure(lambda n=name, m=model: storage.load_list(n, m), repeats)
            for name, model, count in (("exams.json", Exam, exam_count),
                                       ("questions.json", Question, question_count),
                                       ("practice_sessions.json", PracticeSession, session_count))
        }

        progression_result = progression_summary(storage.load_list("exams.json", Exam), today=TODAY)
        expected_progression = _expected_progression(exams)
        assert_oracle(progression_result, expected_progression, "mixed progression")
        progression = measure(lambda: progression_summary(
            storage.load_list("exams.json", Exam), today=TODAY), repeats)
        priority_result = topic_priorities(
            storage.load_list("questions.json", Question), today=TODAY,
            exams=storage.load_list("exams.json", Exam))
        expected_priorities = _expected_priorities(questions, exams)
        assert_oracle(priority_result, expected_priorities, "mixed question priorities")
        assert priority_result["pending_questions"] > 0 and priority_result["scheduled_questions"] > 0
        assert priority_result["today_questions"] > 0
        assert priority_result["today_correct"] > 0 and priority_result["today_incorrect"] > 0
        priorities = measure(lambda: topic_priorities(
            storage.load_list("questions.json", Question), today=TODAY,
            exams=storage.load_list("exams.json", Exam)), repeats)
        expected_practice = _expected_practice(sessions)
        practice_result = practice_topic_summaries(storage.load_list("practice_sessions.json", PracticeSession))
        assert_oracle(practice_result, expected_practice, "mixed practice groups")
        boundary_versions = [
            row for row in practice_result
            if row["subject"].casefold() == "matematik" and row["topic"].casefold() == "boundary"
            and row["scoring_profile"]["profile_id"] == "benchmark-mixed"
        ]
        assert [row["scoring_profile"]["version"] for row in boundary_versions] == [1, 2]
        assert boundary_versions[0]["net"] != boundary_versions[1]["net"]
        oracle_self_checks = [
            probe_oracle_self_check(progression_result, expected_progression,
                                   lambda value: value.__setitem__("total_xp", value["total_xp"] + 1),
                                   "mixed progression XP corrupted"),
            probe_oracle_self_check(priority_result, expected_priorities,
                                   lambda value: value["reviews"].pop(),
                                   "mixed review row omitted"),
            probe_oracle_self_check(practice_result, expected_practice,
                                   lambda rows: rows[0]["trend"].pop(),
                                   "mixed practice trend omitted"),
        ]
        summaries = measure(lambda: practice_topic_summaries(
            storage.load_list("practice_sessions.json", PracticeSession)), repeats)

        update_ids = [f"question-{index}" for index in range(question_count - 11, question_count)]
        update = measure(lambda: _update_question(storage, update_ids.pop(), "[Reading Slip]"), 10)
        mutation_state = storage.load_list("questions.json", Question)
        assert all(q.hamartia_tag == "[Reading Slip]" for q in mutation_state[-11:])
        expected_question_rows = [q.model_dump(mode="json") for q in questions]
        for row in expected_question_rows[-11:]:
            row["hamartia_tag"] = "[Reading Slip]"
        assert_oracle([q.model_dump(mode="json") for q in mutation_state], expected_question_rows,
                      "mixed full question state after update")

        delete_ids = [f"question-{index}" for index in range(question_count - 22, question_count - 11)]
        delete = measure(lambda: _delete_question(storage, delete_ids.pop()), 10)
        remaining = storage.load_list("questions.json", Question)
        removed = {
            *(f"question-{i}" for i in range(question_count - 22, question_count - 11)),
        }
        expected_question_rows = [row for row in expected_question_rows if row["id"] not in removed]
        assert_oracle([q.model_dump(mode="json") for q in remaining], expected_question_rows,
                      "mixed full question state after delete")

        concurrent_inputs = [{
            "id": f"concurrent-{i}", "date": TODAY.isoformat(), "exam_type": "branch",
            "subject": ("Matematik", "Türkçe", "Fizik", "Kimya")[i % 4],
            "correct": 1 + i % 9, "incorrect": i % 4, "blank": i % 3,
            "duration_minutes": i % 7, "duration_seconds": i * 3,
            "created_at": "2026-11-14T12:00:00Z", "sections": [],
        } for i in range(16)]
        concurrent = [Exam(**item) for item in concurrent_inputs]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item: storage.append_list("exams.json", item, Exam), concurrent))
        concurrent_seconds = time.perf_counter() - started
        final_exams = storage.load_list("exams.json", Exam)
        assert len(final_exams) == exam_count + len(concurrent)
        actual_concurrent = sorted(
            (item.model_dump(mode="json") for item in final_exams if item.id.startswith("concurrent-")),
            key=lambda item: item["id"],
        )
        expected_concurrent = []
        for item in concurrent_inputs:
            net = item["correct"] - item["incorrect"] / 4
            duration = item["duration_minutes"] or 1
            xp = max(0, int(net * item["correct"] * 1.5
                            - duration * item["incorrect"] * 0.25))
            expected_concurrent.append({
                **item, "total": item["correct"] + item["incorrect"], "net": net, "xp": xp,
                "scoring_profile": {
                    "profile_id": "legacy-yks", "version": 1,
                    "display_name": "YKS (legacy)", "country_label": "Türkiye",
                    "scoring_rule": {
                        "correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1",
                    },
                },
            })
        expected_concurrent.sort(key=lambda item: item["id"])
        assert_oracle(actual_concurrent, expected_concurrent, "mixed concurrent append full records")

        emit({
            "benchmark": "persisted_mixed_study_workloads", "seed": SEED,
            "records": {"exams": exam_count, "questions": question_count, "practice_sessions": session_count},
            "persisted_json_bytes": persisted_bytes,
            "upload_fixtures": {
                "files": len(image_files),
                "bytes": sum(map(len, image_files.values())),
                "size_range_bytes": [min(map(len, image_files.values())), max(map(len, image_files.values()))],
                "referenced_questions": sum(bool(question.image_path) for question in questions),
                "question_text_characters": sum(len(question.ocr_text) for question in questions),
                "ocr_text_length_classes": "short, paragraph, and long-passage records",
                "image_dimension_classes": sorted({
                    ("320x240", "640x480", "1024x768")[int(name[2:7]) % 3]
                    for name in image_files
                }),
            },
            "first_service_load_seconds": first_service_load, "warm_load": warm,
            "progression_full_history": progression, "question_insights_full_history": priorities,
            "practice_summaries_full_history": summaries,
            "question_review_activity": {key: priority_result[key] for key in (
                "pending_questions", "scheduled_questions", "today_questions", "today_correct", "today_incorrect")},
            "question_update_10_records": update, "question_delete_10_records": delete,
            "concurrent_appends": {"workers": 4, "records": len(concurrent), "seconds": round(concurrent_seconds, 6)},
            "correctness": "progression, due/scheduled and same-day review activity, order insights, practice groups/trends, mutations, and every concurrent appended field match independent oracles",
            "oracle_self_checks": oracle_self_checks,
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
            assert question.subject in ("", exam.subject)
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
    last = max((day for day in dates if day <= TODAY), default=None)
    streak = 0
    if last and last >= TODAY - timedelta(days=1):
        while last - timedelta(days=streak) in dates:
            streak += 1
    return {"total_xp": xp, "level": xp // 500 + 1 if xp >= 500 else 1,
            "streak_days": streak, "last_active_date": last.isoformat() if last else ""}


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
            day = _oracle_attempt_day(attempt)
            if day == TODAY:
                today_ids.add(question.id)
                today_correct += int(attempt.correct)
                today_incorrect += int(not attempt.correct)

        if question.review_attempts:
            attempts = question.review_attempts
            last_day = _oracle_attempt_day(attempts[-1])
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
        subject = question.subject.strip()
        topic = question.topic.strip()
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
        if question.reviewed_at:
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
        "curriculum_references": _expected_curriculum_references(questions),
    }


def _expected_curriculum_references(questions, limit=8):
    # The fixture places B, A, and C on the final three questions.
    # This explicit oracle checks full values, defaults, and reverse insertion order.
    rows = [
        {
            "subject": questions[-1].subject, "framework": "Synthetic framework B",
            "source": "Benchmark fixture B", "version": "v2", "grade_year": "Year 2",
            "unit_theme": "Made-up unit B", "learning_outcome": "Explain invented pattern B",
            "process_component": "Reasoning B", "source_url": "",
        },
        {
            "subject": questions[-2].subject, "framework": "Synthetic framework A",
            "source": "Benchmark fixture A", "version": "v1", "grade_year": "Year 1",
            "unit_theme": "Made-up unit A", "learning_outcome": "Explain invented pattern A",
            "process_component": "Reasoning A", "source_url": "",
        },
        {
            "subject": questions[-3].subject, "framework": "Synthetic framework C",
            "source": "Benchmark fixture C", "version": "v3", "grade_year": "Year 3",
            "unit_theme": "Made-up unit C", "learning_outcome": "Explain invented pattern C",
            "process_component": "Reasoning C", "source_url": "",
        },
    ]
    return rows[:limit]


def _expected_practice(sessions):
    groups = {}
    for session in sessions:
        profile_key = (session.scoring_profile.profile_id, session.scoring_profile.version)
        key = (*profile_key, session.subject.strip().casefold(), session.topic.strip().casefold())
        profile_snapshot = PRACTICE_PROFILE_FIXTURES[profile_key]
        group = groups.setdefault(key, {
            "subject": session.subject, "topic": session.topic, "sessions": [],
            "scoring_profile": profile_snapshot,
            "correct": 0, "incorrect": 0, "blank": 0,
        })
        group["sessions"].append(session)
        for field in ("correct", "incorrect", "blank"):
            group[field] += getattr(session, field)
    result = []
    for group in groups.values():
        ordered = sorted(group.pop("sessions"), key=lambda item: (item.date, item.created_at, item.id))
        answered = group["correct"] + group["incorrect"]
        rule = group["scoring_profile"]["scoring_rule"]

        def literal_net(item):
            return float(
                item.correct * Fraction(rule["correct_points"])
                - item.incorrect * Fraction(rule["wrong_penalty"])
                + item.blank * Fraction(rule["blank_points"])
            )

        group.update({
            "session_count": len(ordered), "answered": answered,
            "net": sum(literal_net(item) for item in ordered),
            "accuracy": group["correct"] / answered if answered else None,
            "trend": [{
                "id": item.id, "date": item.date,
                "net": literal_net(item),
                "accuracy": item.correct / (item.correct + item.incorrect) if item.correct + item.incorrect else None,
            } for item in ordered],
        })
        result.append(group)
    result.sort(key=lambda item: (
        item["subject"].casefold(), item["topic"].casefold(),
        item["scoring_profile"]["profile_id"], item["scoring_profile"]["version"],
    ))
    return result


def _oracle_attempt_day(attempt):
    try:
        parsed = date.fromisoformat(attempt.attempt_day)
        if parsed.isoformat() == attempt.attempt_day:
            return parsed
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(attempt.attempted_at.replace("Z", "+00:00")).date()
    except (AttributeError, ValueError):
        return None


def _assert_count(storage, name, model, count):
    assert len(storage.load_list(name, model)) == count


def _update_question(storage, question_id, tag):
    def update(items):
        for item in items:
            if item.id == question_id:
                item.hamartia_tag = tag
                return True
        return False
    return storage.update_list("questions.json", Question, update)


def _delete_question(storage, question_id):
    def delete(items):
        for index, item in enumerate(items):
            if item.id == question_id:
                items.pop(index)
                return True
        return False
    return storage.update_list("questions.json", Question, delete)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exams", type=int, default=1500)
    parser.add_argument("--questions", type=int, default=2500)
    parser.add_argument("--sessions", type=int, default=4000)
    parser.add_argument("--repeats", type=int, default=21)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    run(args.exams, args.questions, args.sessions, args.repeats, args.json_output)
