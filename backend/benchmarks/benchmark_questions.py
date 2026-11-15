"""Measure local question-image storage and tagging without calling a model."""

import asyncio
import hashlib
import json
import random
import tempfile
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.api import questions
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question, ReviewAttempt
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, probe_oracle_self_check, seeded_photo_png, seeded_png

SEED = 20261114
TODAY = date(2026, 11, 14)
FIXED_NOW = "2026-11-14T10:00:00Z"
SUBJECTS = ("Matematik", "Türkçe", "Fizik")
TOPICS = ("Fonksiyonlar", "Paragraf", "Hareket", "Denklemler")

def make_upload(index):
    file = tempfile.SpooledTemporaryFile()
    width, height = ((256, 256), (512, 384), (1024, 768))[index % 3]
    rng = random.Random(SEED + index)
    pixels = seeded_photo_png(width, height, rng) if index % 3 == 0 else seeded_png(width, height, rng)
    file.write(pixels)
    file.seek(0)
    return UploadFile(
        filename=f"question-{index}.png",
        file=file,
        headers=Headers({"content-type": "image/png"}),
    )


async def run(count=24, repeats=7, json_output=None):
    if not 2 * repeats + 3 <= count <= 30 or not 3 <= repeats <= 11:
        raise ValueError("count must be 2*repeats+3..30 and repeats 3..11")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        storage = StorageService(root)
        sectioned_exam = Exam(
            id="benchmark-tyt", date="2026-11-14", exam_type="tyt", subject="TYT Geneli",
            correct=85, incorrect=22, blank=13,
            sections=[
                {"subject": "Türkçe", "correct": 30, "incorrect": 7, "blank": 3},
                {"subject": "Matematik", "correct": 27, "incorrect": 8, "blank": 5},
                {"subject": "Fen", "correct": 13, "incorrect": 4, "blank": 3},
                {"subject": "Sosyal", "correct": 15, "incorrect": 3, "blank": 2},
            ],
        )
        storage.save_list("exams.json", [sectioned_exam])
        with patch.object(questions, "DATA_DIR", root), patch.object(questions, "UPLOAD_DIR", root / "uploads"), \
                patch.object(questions, "_utcnow", return_value=FIXED_NOW):
            fixture_started = time.perf_counter()
            upload_fixtures = [make_upload(index) for index in range(count)]
            upload_fixture_generation_seconds = time.perf_counter() - fixture_started
            upload_fixture_bytes = 0
            upload_fixture_hashes = []
            for upload in upload_fixtures:
                upload.file.seek(0)
                contents = upload.file.read()
                upload_fixture_bytes += len(contents)
                upload_fixture_hashes.append(hashlib.sha256(contents).hexdigest())
                upload.file.seek(0)

            started = time.perf_counter()
            uploaded_records = []
            for index, upload in enumerate(upload_fixtures):
                try:
                    uploaded_records.append(await questions.upload_question(
                        upload, f"Seeded question text {index}", SUBJECTS[(index // 4) % len(SUBJECTS)],
                        TOPICS[index % len(TOPICS)], storage,
                    ))
                finally:
                    await upload.close()
            upload_seconds = time.perf_counter() - started

            started = time.perf_counter()
            saved = await questions.list_questions(storage)
            list_seconds = time.perf_counter() - started
            assert len(saved) == count
            expected_questions = [Question(
                id=item.id, image_name=item.image_name, image_path=f"uploads/{item.image_name}",
                ocr_text=f"Seeded question text {index}",
                subject=SUBJECTS[(index // 4) % len(SUBJECTS)], topic=TOPICS[index % len(TOPICS)],
                created_at=FIXED_NOW,
            ) for index, item in enumerate(uploaded_records)]
            uploaded_ids = [item.id for item in uploaded_records]
            assert len(set(uploaded_ids)) == count, "upload API returned duplicate question IDs"
            assert len({item.id for item in saved}) == count, "persisted question IDs are not unique"
            assert len({item.image_name for item in saved}) == count, "persisted upload filenames are not unique"
            assert all(item.id.startswith("q_") and item.image_name.startswith("q_")
                       and item.image_path == f"uploads/{item.image_name}" for item in saved)
            assert [item.id for item in saved] == uploaded_ids
            expected_upload_hashes = {item.image_name: upload_fixture_hashes[index]
                                      for index, item in enumerate(uploaded_records)}
            actual_upload_hashes = {
                item.image_name: hashlib.sha256((root / item.image_path).read_bytes()).hexdigest()
                for item in saved
            }
            assert actual_upload_hashes == expected_upload_hashes
            assert sum((root / item.image_path).stat().st_size for item in saved) == upload_fixture_bytes
            assert_oracle([item.model_dump(mode="json") for item in saved],
                          [item.model_dump(mode="json") for item in expected_questions],
                          "full uploaded question records")
            list_stats = await _measure_async(lambda: questions.list_questions(storage), repeats)
            assert list_stats.pop("last_result_count") == count

            for index, item in enumerate(saved):
                if index % 5 == 0:
                    await questions.tag_question(item.id, questions.TagRequest(hamartia_tag="[Reading Slip]"), storage)
                    expected_questions[index].hamartia_tag = "[Reading Slip]"
                elif index % 7 == 0:
                    await questions.tag_question(item.id, questions.TagRequest(hamartia_tag="[Distractor Trap]"), storage)
                    expected_questions[index].hamartia_tag = "[Distractor Trap]"
            saved = await questions.list_questions(storage)
            assert_oracle([item.model_dump(mode="json") for item in saved],
                          [item.model_dump(mode="json") for item in expected_questions],
                          "full question records after tagging")

            started = time.perf_counter()
            insights = await questions.question_insights(storage, today=TODAY)
            insight_seconds = time.perf_counter() - started
            expected_insights = _expected_insights(expected_questions, TODAY, [sectioned_exam])
            assert_oracle(insights, expected_insights, "question insights full output")
            oracle_self_checks = [probe_oracle_self_check(
                insights, expected_insights,
                lambda output: output["topics"][0].__setitem__("pending_count", -1),
                "question pending count corrupted",
            )]
            insight_stats = await _measure_async(lambda: questions.question_insights(storage, today=TODAY), repeats)
            assert insight_stats.pop("last_result_count") == count

            image = await questions.get_question_image(saved[0].id, storage)
            assert Path(image.path).is_file()
            await questions.tag_question(saved[0].id, questions.TagRequest(hamartia_tag="[Reading Slip]"), storage)
            started = time.perf_counter()
            await questions.record_question_attempt(
                saved[0].id, questions.AttemptRequest(correct=False, attempt_day=TODAY), storage,
            )
            attempt_seconds = time.perf_counter() - started
            started = time.perf_counter()
            await questions.review_question(saved[0].id, questions.ReviewRequest(), storage)
            review_seconds = time.perf_counter() - started

            started = time.perf_counter()
            await questions.update_question(
                saved[0].id,
                questions.QuestionUpdate(subject="Matematik", topic="Denklemler", ocr_text="Düzenlenmiş soru"),
                storage,
            )
            update_seconds = time.perf_counter() - started
            expected_by_id = {item.id: item for item in expected_questions}
            expected_first = expected_by_id[saved[0].id]
            expected_first.review_attempts.append(ReviewAttempt(
                attempted_at=FIXED_NOW, attempt_day=TODAY.isoformat(), correct=False,
            ))
            expected_first.reviewed_at = FIXED_NOW
            expected_first.subject = "Matematik"
            expected_first.topic = "Denklemler"
            expected_first.ocr_text = "Düzenlenmiş soru"
            update_target_ids = [item.id for item in saved[1:repeats + 2]]
            update_ids = list(update_target_ids)
            update_samples = await _measure_async(lambda: _update_one(questions, storage, update_ids.pop()), repeats)
            assert update_samples.pop("last_result_count") == 1
            for question_id in update_target_ids:
                expected_by_id[question_id].subject = "Matematik"
                expected_by_id[question_id].topic = "Denklemler"
                expected_by_id[question_id].ocr_text = "Updated seeded question"
            started = time.perf_counter()
            await questions.delete_question(saved[0].id, storage)
            delete_seconds = time.perf_counter() - started
            assert not (root / "uploads" / saved[0].image_name).exists()
            delete_ids = [item.id for item in saved[repeats + 2:2 * repeats + 3]]
            delete_samples = await _measure_async(lambda: questions.delete_question(delete_ids.pop(), storage), repeats)
            assert delete_samples.pop("last_result_count") == 1
            saved_after_mutations = storage.load_list("questions.json", Question)
            deleted_ids = {saved[index].id for index in range(repeats + 2, 2 * repeats + 3)}
            deleted_ids.add(saved[0].id)
            expected_questions = [item for item in expected_questions if item.id not in deleted_ids]
            assert_oracle([item.model_dump(mode="json") for item in saved_after_mutations],
                          [item.model_dump(mode="json") for item in expected_questions],
                          "full records after attempts, edits, and deletes")

            started = time.perf_counter()
            text_created = []
            for index in range(count):
                text_created.append(await questions.upload_question(
                    None, f"Metin sorusu {index}", "Türkçe", "Paragraf", storage,
                ))
            text_capture_seconds = time.perf_counter() - started
            saved_after_text = storage.load_list("questions.json", Question)
            expected_text = [Question(
                id=item.id, ocr_text=f"Metin sorusu {index}", subject="Türkçe", topic="Paragraf",
                created_at=FIXED_NOW,
            ) for index, item in enumerate(text_created)]
            assert all(item.id.startswith("q_") and not item.image_path for item in text_created)
            expected_questions.extend(expected_text)
            assert_oracle([item.model_dump(mode="json") for item in saved_after_text],
                          [item.model_dump(mode="json") for item in expected_questions],
                          "full records after text capture")

            section_count = min(count, 40)
            started = time.perf_counter()
            section_created = []
            for index in range(section_count):
                section_created.append(await questions.upload_question(
                    None, f"TYT Türkçe {index}", "Türkçe", "Paragraf", storage,
                    exam_id=sectioned_exam.id, question_number=index + 1,
                    solve_order=index + 1, time_spent_seconds=30,
                ))
            section_question_upload_seconds = time.perf_counter() - started
            saved_after_sections = storage.load_list("questions.json", Question)
            section_questions = [item for item in saved_after_sections if item.exam_id == sectioned_exam.id]
            expected_section = [Question(
                id=item.id, ocr_text=f"TYT Türkçe {index}", subject="Türkçe", topic="Paragraf",
                created_at=FIXED_NOW, exam_id=sectioned_exam.id,
                question_number=index + 1, solve_order=index + 1, time_spent_seconds=30,
                exam_section_total=40,
            ) for index, item in enumerate(section_created)]
            assert all(item.id.startswith("q_") for item in section_created)
            expected_questions.extend(expected_section)
            assert_oracle([item.model_dump(mode="json") for item in saved_after_sections],
                          [item.model_dump(mode="json") for item in expected_questions],
                          "full records after section-linked capture")
            started = time.perf_counter()
            section_insights = topic_priorities(
                storage.load_list("questions.json", Question), exams=[sectioned_exam],
            )["question_order"]
            section_insight_seconds = time.perf_counter() - started
            assert len(section_insights) == 1 and section_insights[0]["subject"] == "Türkçe"
            expected_final_insights = _expected_insights(expected_questions, TODAY, [sectioned_exam])
            actual_final_insights = await questions.question_insights(storage, today=TODAY)
            assert_oracle(actual_final_insights, expected_final_insights,
                          "full insights after all question mutations and captures")
            code_path_fault_probes = await _run_code_path_fault_probes()

            # Invalid boundary inputs must fail without leaving partial records.
            before_rejections = storage.load_list("questions.json", Question)
            for upload, text, expected_status in (
                (None, "   ", 422),
                (UploadFile(filename="bad.png", file=tempfile.SpooledTemporaryFile(),
                            headers=Headers({"content-type": "image/png"})), "", 415),
            ):
                if upload is not None:
                    upload.file.write(b"not-a-png")
                    upload.file.seek(0)
                try:
                    try:
                        await questions.upload_question(upload, text, "Matematik", "Boundary", storage)
                    except HTTPException as error:
                        assert error.status_code == expected_status
                    else:
                        raise AssertionError("invalid question upload was accepted")
                finally:
                    if upload is not None:
                        await upload.close()
            assert_oracle([q.model_dump(mode="json") for q in storage.load_list("questions.json", Question)],
                          [q.model_dump(mode="json") for q in before_rejections], "rejected uploads leave storage unchanged")

        emit({
            "benchmark": "local_question_flow",
            "seed": SEED,
            "questions": count,
            "valid_png_dimensions": ["256x256", "512x384", "1024x768"],
            "image_bytes": upload_fixture_bytes,
            "upload_fixture_generation_seconds": round(upload_fixture_generation_seconds, 4),
            "upload_seconds": round(upload_seconds, 4),
            "uploads_per_second": round(count / upload_seconds, 2),
            "list_seconds": round(list_seconds, 4),
            "list_warm": list_stats,
            "insight_seconds": round(insight_seconds, 4),
            "insights_warm": insight_stats,
            "attempt_seconds": round(attempt_seconds, 4),
            "review_seconds": round(review_seconds, 4),
            "update_seconds": round(update_seconds, 4),
            "repeated_updates": update_samples,
            "delete_seconds": round(delete_seconds, 4),
            "repeated_deletes": delete_samples,
            "text_capture_seconds": round(text_capture_seconds, 4),
            "text_captures_per_second": round(count / text_capture_seconds, 2),
            "section_questions": section_count,
            "section_question_upload_seconds": round(section_question_upload_seconds, 4),
            "section_question_insight_seconds": round(section_insight_seconds, 4),
            "correctness": "full persisted records and full insights matched independent oracles after upload, tagging, attempt, edit, delete, and section-linked capture",
            "oracle_self_checks": oracle_self_checks,
            "code_path_fault_probes": code_path_fault_probes,
            "fault_probe_timing": "excluded from all reported performance samples",
            "rejected_uploads": ["blank text", "invalid PNG signature"],
            "limitations": "PNG fixtures mix seeded block-textured and high-entropy pixels; no real corpus or AI/image-understanding path is used.",
        }, json_output)


async def _measure_async(operation, repeats):
    for _ in range(1):
        await operation()
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = await operation()
        samples.append(time.perf_counter() - started)
    ordered = sorted(samples)
    from statistics import median
    return {"samples": repeats, "p50_seconds": round(median(samples), 6),
            "p95_seconds": round(ordered[max(0, (repeats * 95 + 99) // 100 - 1)], 6),
            "last_result_count": len(result) if isinstance(result, list) else
            result.get("total_questions", 1) if isinstance(result, dict) else 1}


async def _update_one(api, storage, question_id):
    return await api.update_question(
        question_id,
        api.QuestionUpdate(subject="Matematik", topic="Denklemler", ocr_text="Updated seeded question"),
        storage,
    )


async def _run_code_path_fault_probes():
    """Inject seeded persistence faults through real question API operations.

    Probes run outside timing and require the independent full-record oracle
    to detect each false-success result.
    """
    detected = []
    with tempfile.TemporaryDirectory(prefix="hamartia-question-faults-") as directory:
        root = Path(directory)
        storage = StorageService(root)
        with patch.object(questions, "DATA_DIR", root), patch.object(questions, "UPLOAD_DIR", root / "uploads"), \
                patch.object(questions, "_utcnow", return_value=FIXED_NOW):
            original_write = storage._write_atomic

            def write_without_last_question(filename, payload):
                if filename == "questions.json":
                    rows = json.loads(payload)
                    rows.pop()
                    payload = json.dumps(rows)
                return original_write(filename, payload)

            with patch.object(storage, "_write_atomic", side_effect=write_without_last_question), \
                    patch.object(questions, "uuid4", side_effect=[
                        SimpleNamespace(hex="fault-upload-file"),
                        SimpleNamespace(hex="fault-upload-record"),
                    ]):
                upload = make_upload(991)
                try:
                    created = await questions.upload_question(
                        upload, "Fault-probe image question", "Matematik", "Denklemler", storage,
                    )
                finally:
                    await upload.close()
            expected_created = Question(
                id="q_fault-upload-record", image_name="q_fault-upload-file.png",
                image_path="uploads/q_fault-upload-file.png",
                ocr_text="Fault-probe image question", subject="Matematik", topic="Denklemler",
                created_at=FIXED_NOW,
            )
            assert created.id == expected_created.id and created.image_name == expected_created.image_name
            actual = [item.model_dump(mode="json") for item in storage.load_list("questions.json", Question)]
            expected = [expected_created.model_dump(mode="json")]
            detected.append(_require_fault_detected(actual, expected, "lost upload append"))

            base = Question(id="fault-review", subject="Türkçe", topic="Paragraf",
                            ocr_text="Fault-probe review question", created_at=FIXED_NOW)
            storage.save_list("questions.json", [base])
            expected_review = base.model_copy(deep=True)
            expected_review.review_attempts.append(ReviewAttempt(
                attempted_at=FIXED_NOW, attempt_day=TODAY.isoformat(), correct=False,
            ))
            def write_without_review_attempt(filename, payload):
                if filename == "questions.json":
                    rows = json.loads(payload)
                    for row in rows:
                        if row["id"] == base.id:
                            row["review_attempts"] = []
                    payload = json.dumps(rows)
                return original_write(filename, payload)

            with patch.object(storage, "_write_atomic", side_effect=write_without_review_attempt):
                returned = await questions.record_question_attempt(
                    base.id, questions.AttemptRequest(correct=False, attempt_day=TODAY), storage,
                )
            assert returned.review_attempts, "fault probe did not exercise successful API response path"
            actual = [item.model_dump(mode="json") for item in storage.load_list("questions.json", Question)]
            expected = [expected_review.model_dump(mode="json")]
            detected.append(_require_fault_detected(actual, expected, "lost persisted review attempt"))
    return detected


def _require_fault_detected(actual, expected, label):
    try:
        assert_oracle(actual, expected, label)
    except AssertionError:
        return label
    raise AssertionError(f"independent full-record oracle missed injected {label} fault")


def _expected_insights(records, today, exams=()):
    groups = {}
    pending = []
    scheduled = 0
    unclassified = 0
    today_ids = set()
    today_correct = 0
    today_incorrect = 0
    for item in records:
        for attempt in item.review_attempts:
            attempt_day = _oracle_attempt_day(attempt)
            if attempt_day == today:
                today_ids.add(item.id)
                if attempt.correct:
                    today_correct += 1
                else:
                    today_incorrect += 1
        state = _oracle_review_state(item, today)
        if not state["due"]:
            if state["due_date"]:
                scheduled += 1
            continue
        pending.append(item)
        unclassified += not item.subject.strip() or not item.topic.strip()
        key = (item.subject.strip().casefold(), item.topic.strip().casefold())
        group = groups.setdefault(key, {"subject": item.subject.strip(), "topic": item.topic.strip(),
                                        "pending_count": 0, "last_seen": "", "tags": Counter()})
        group["pending_count"] += 1
        group["last_seen"] = max(group["last_seen"], item.created_at[:10])
        group["tags"][item.hamartia_tag] += 1
    topics = [{**group, "tags": dict(group["tags"])} for group in groups.values()]
    topics.sort(key=lambda row: (-row["pending_count"], row["subject"].casefold(), row["topic"].casefold()))
    reviews = [{"id": item.id, "subject": item.subject.strip(), "topic": item.topic.strip(),
                "hamartia_tag": item.hamartia_tag, "ocr_text": item.ocr_text,
                "has_image": bool(item.image_path), **_oracle_review_state(item, today)} for item in pending]
    reviews.sort(key=lambda item: (item["due_date"], item["subject"].casefold(), item["topic"].casefold(), item["id"]))
    return {
        "total_questions": len(records), "pending_questions": len(pending),
        "scheduled_questions": scheduled, "unclassified_questions": unclassified,
        "today_questions": len(today_ids), "today_correct": today_correct, "today_incorrect": today_incorrect,
        "question_order": _expected_question_order(records, exams), "topics": topics, "reviews": reviews,
        "curriculum_references": [],
    }


def _oracle_attempt_day(attempt):
    try:
        parsed = date.fromisoformat(attempt.attempt_day)
        if parsed.isoformat() == attempt.attempt_day:
            return parsed
    except (TypeError, ValueError):
        pass
    try:
        return date.fromisoformat(attempt.attempted_at.replace("Z", "+00:00")[:10])
    except (AttributeError, ValueError):
        return None


def _oracle_review_state(question, today):
    if question.reviewed_at:
        return {"due_date": "", "due": False, "streak": 0, "last_correct": None}
    if not question.review_attempts:
        return {"due_date": today.isoformat(), "due": True, "streak": 0, "last_correct": None}
    attempts = question.review_attempts
    last = attempts[-1]
    last_day = _oracle_attempt_day(last)
    if last_day is None:
        return {"due_date": today.isoformat(), "due": True, "streak": 0, "last_correct": last.correct}
    streak = 0
    for attempt in reversed(attempts):
        if not attempt.correct:
            break
        streak += 1
    interval = (1, 3, 7, 14, 30)[min(streak - 1, 4)] if streak else 1
    due_day = last_day + timedelta(days=interval)
    return {"due_date": due_day.isoformat(), "due": due_day <= today,
            "streak": streak, "last_correct": last.correct}


def _expected_question_order(records, exams):
    by_id = {exam.id: exam for exam in exams}
    groups = {}
    for question in records:
        exam = by_id.get(question.exam_id)
        if not exam or question.solve_order is None:
            continue
        size = question.exam_section_total or exam.correct + exam.incorrect + exam.blank
        if size < 1 or question.solve_order > size:
            continue
        subject = question.subject if question.exam_section_total else exam.subject
        key = (exam.exam_type or "branch", subject)
        group = groups.setdefault(key, {"exam_ids": set(), "early": [], "middle": [], "late": []})
        group["exam_ids"].add(exam.id)
        stage = ("early", "middle", "late")[min(2, ((question.solve_order - 1) * 3) // size)]
        group[stage].append(question.time_spent_seconds)
    output = []
    for (exam_type, subject), group in groups.items():
        row = {"exam_type": exam_type, "subject": subject, "exam_count": len(group["exam_ids"])}
        for stage, values in ((name, group[name]) for name in ("early", "middle", "late")):
            valid = [value for value in values if value is not None]
            row[stage] = {"wrong_count": len(values), "median_seconds": median(valid) if valid else None}
        output.append(row)
    return sorted(output, key=lambda row: (-sum(row[stage]["wrong_count"] for stage in ("early", "middle", "late")),
                                           row["subject"].casefold(), row["exam_type"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    asyncio.run(run(args.count, args.repeats, args.json_output))
