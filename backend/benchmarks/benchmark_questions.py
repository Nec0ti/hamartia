"""Measure local question-image storage and tagging without calling a model."""

import asyncio
import json
import random
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.api import questions
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, probe_detects_mutation, seeded_png

SEED = 20261114
TODAY = date(2026, 11, 14)
RNG = random.Random(SEED)

def make_upload(index):
    file = tempfile.SpooledTemporaryFile()
    width, height = ((256, 256), (512, 384), (1024, 768))[index % 3]
    file.write(seeded_png(width, height, RNG))
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
        with patch.object(questions, "DATA_DIR", root), patch.object(questions, "UPLOAD_DIR", root / "uploads"):
            started = time.perf_counter()
            for index in range(count):
                upload = make_upload(index)
                try:
                    await questions.upload_question(upload, "Soru metni", "Matematik", "Fonksiyonlar", storage)
                finally:
                    await upload.close()
            upload_seconds = time.perf_counter() - started

            started = time.perf_counter()
            saved = await questions.list_questions(storage)
            list_seconds = time.perf_counter() - started
            assert len(saved) == count
            list_stats = await _measure_async(lambda: questions.list_questions(storage), repeats)
            assert list_stats.pop("last_result_count") == count

            started = time.perf_counter()
            insights = await questions.question_insights(storage, today=TODAY)
            insight_seconds = time.perf_counter() - started
            expected_insights = _expected_insights(saved, TODAY)
            assert_oracle(insights, expected_insights, "question insights full output")
            mutation_probes = [probe_detects_mutation(
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
                saved[0].id, questions.AttemptRequest(correct=False), storage,
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
            update_target_ids = [item.id for item in saved[1:repeats + 2]]
            update_ids = list(update_target_ids)
            update_samples = await _measure_async(lambda: _update_one(questions, storage, update_ids.pop()), repeats)
            assert update_samples.pop("last_result_count") == 1
            started = time.perf_counter()
            await questions.delete_question(saved[0].id, storage)
            delete_seconds = time.perf_counter() - started
            assert not (root / "uploads" / saved[0].image_name).exists()
            delete_ids = [item.id for item in saved[repeats + 2:2 * repeats + 3]]
            delete_samples = await _measure_async(lambda: questions.delete_question(delete_ids.pop(), storage), repeats)
            assert delete_samples.pop("last_result_count") == 1
            saved_after_mutations = storage.load_list("questions.json", Question)
            assert all(next(item for item in saved_after_mutations if item.id == question_id).ocr_text == "Updated seeded question"
                       for question_id in update_target_ids)
            deleted_ids = {saved[index].id for index in range(repeats + 2, 2 * repeats + 3)}
            assert not any(item.id in deleted_ids for item in saved_after_mutations)

            started = time.perf_counter()
            for index in range(count):
                await questions.upload_question(
                    None, f"Metin sorusu {index}", "Türkçe", "Paragraf", storage,
                )
            text_capture_seconds = time.perf_counter() - started
            saved_after_text = storage.load_list("questions.json", Question)
            assert len(saved_after_text) == 2 * count - repeats - 2
            assert sum(not item.image_path and item.ocr_text.startswith("Metin sorusu ") for item in saved_after_text) == count

            section_count = min(count, 40)
            started = time.perf_counter()
            for index in range(section_count):
                await questions.upload_question(
                    None, f"TYT Türkçe {index}", "Türkçe", "Paragraf", storage,
                    exam_id=sectioned_exam.id, question_number=index + 1,
                    solve_order=index + 1, time_spent_seconds=30,
                )
            section_question_upload_seconds = time.perf_counter() - started
            saved_after_sections = storage.load_list("questions.json", Question)
            section_questions = [item for item in saved_after_sections if item.exam_id == sectioned_exam.id]
            assert len(section_questions) == section_count
            assert all(1 <= item.question_number <= 40 and 1 <= item.solve_order <= 40 for item in section_questions)
            started = time.perf_counter()
            section_insights = topic_priorities(
                storage.load_list("questions.json", Question), exams=[sectioned_exam],
            )["question_order"]
            section_insight_seconds = time.perf_counter() - started
            assert len(section_insights) == 1 and section_insights[0]["subject"] == "Türkçe"

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
            "image_bytes": sum(path.stat().st_size for path in (root / "uploads").iterdir()),
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
            "correctness": "upload, query, edit, attempt, review, and deletion assertions passed",
            "mutation_probes": mutation_probes,
            "rejected_uploads": ["blank text", "invalid PNG signature"],
            "limitations": "PNG pixels are deterministic synthetic noise; no AI or image-understanding path is called.",
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


def _expected_insights(records, today):
    tag_counts = Counter(item.hamartia_tag for item in records)
    topic = {
        "subject": "Matematik", "topic": "Fonksiyonlar", "pending_count": len(records),
        "last_seen": max(item.created_at[:10] for item in records), "tags": dict(tag_counts),
    }
    reviews = [{
        "id": item.id, "subject": item.subject, "topic": item.topic,
        "hamartia_tag": item.hamartia_tag, "ocr_text": item.ocr_text,
        "has_image": bool(item.image_path), "due_date": today.isoformat(),
        "due": True, "streak": 0, "last_correct": None,
    } for item in records]
    reviews.sort(key=lambda item: (item["due_date"], item["subject"].casefold(), item["topic"].casefold(), item["id"]))
    return {
        "total_questions": len(records), "pending_questions": len(records),
        "scheduled_questions": 0, "unclassified_questions": 0,
        "today_questions": 0, "today_correct": 0, "today_incorrect": 0,
        "question_order": [], "topics": [topic], "reviews": reviews,
        "curriculum_references": [],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    asyncio.run(run(args.count, args.repeats, args.json_output))
