"""Measure local question-image storage and tagging without calling a model."""

import asyncio
import json
import random
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api import questions
from app.core.study_plan import topic_priorities
from app.models.schemas import Exam, Question
from app.services.storage import StorageService
from benchmark_common import emit

SEED = 20261114
RNG = random.Random(SEED)

def make_upload(index):
    file = tempfile.SpooledTemporaryFile()
    file.write(b"\x89PNG\r\n\x1a\n" + RNG.randbytes(4096 * (1 + index % 12)))
    file.seek(0)
    return UploadFile(
        filename=f"question-{index}.png",
        file=file,
        headers=Headers({"content-type": "image/png"}),
    )


async def run(count=100, repeats=7, json_output=None):
    if not 1 <= count <= 200 or not 3 <= repeats <= 31:
        raise ValueError("count must be 1..200 and repeats 3..31")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        storage = StorageService(root)
        sectioned_exam = Exam(
            id="benchmark-tyt", date="2026-11-14", exam_type="tyt", subject="TYT Geneli",
            correct=30, incorrect=5, blank=5,
            sections=[{"subject": "Türkçe", "correct": 30, "incorrect": 5, "blank": 5}],
        )
        storage.save_list("exams.json", [sectioned_exam])
        with patch.object(questions, "DATA_DIR", root), patch.object(questions, "UPLOAD_DIR", root / "uploads"):
            started = time.perf_counter()
            for index in range(count):
                await questions.upload_question(
                    make_upload(index), "Soru metni", "Matematik", "Fonksiyonlar", storage,
                )
            upload_seconds = time.perf_counter() - started

            started = time.perf_counter()
            saved = await questions.list_questions(storage)
            list_seconds = time.perf_counter() - started
            assert len(saved) == count
            list_stats = await _measure_async(lambda: questions.list_questions(storage), repeats)
            assert list_stats.pop("last_result_count") == count

            started = time.perf_counter()
            insights = await questions.question_insights(storage)
            insight_seconds = time.perf_counter() - started
            assert insights["total_questions"] == count
            assert insights["topics"][0]["pending_count"] == count
            insight_stats = await _measure_async(lambda: questions.question_insights(storage), repeats)
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
            started = time.perf_counter()
            await questions.delete_question(saved[0].id, storage)
            delete_seconds = time.perf_counter() - started
            assert not (root / "uploads" / saved[0].image_name).exists()

            started = time.perf_counter()
            for index in range(count):
                await questions.upload_question(
                    None, f"Metin sorusu {index}", "Türkçe", "Paragraf", storage,
                )
            text_capture_seconds = time.perf_counter() - started

            section_count = min(count, 40)
            started = time.perf_counter()
            for index in range(section_count):
                await questions.upload_question(
                    None, f"TYT Türkçe {index}", "Türkçe", "Paragraf", storage,
                    exam_id=sectioned_exam.id, question_number=index + 1,
                    solve_order=index + 1, time_spent_seconds=30,
                )
            section_question_upload_seconds = time.perf_counter() - started
            started = time.perf_counter()
            section_insights = topic_priorities(
                storage.load_list("questions.json", Question), exams=[sectioned_exam],
            )["question_order"]
            section_insight_seconds = time.perf_counter() - started
            assert len(section_insights) == 1 and section_insights[0]["subject"] == "Türkçe"

        emit({
            "benchmark": "local_question_flow",
            "seed": SEED,
            "questions": count,
            "synthetic_image_bytes_min": 4096,
            "synthetic_image_bytes_max": 12 * 4096,
            "upload_seconds": round(upload_seconds, 4),
            "uploads_per_second": round(count / upload_seconds, 2),
            "list_seconds": round(list_seconds, 4),
            "list_warm": list_stats,
            "insight_seconds": round(insight_seconds, 4),
            "insights_warm": insight_stats,
            "attempt_seconds": round(attempt_seconds, 4),
            "review_seconds": round(review_seconds, 4),
            "update_seconds": round(update_seconds, 4),
            "delete_seconds": round(delete_seconds, 4),
            "text_capture_seconds": round(text_capture_seconds, 4),
            "text_captures_per_second": round(count / text_capture_seconds, 2),
            "section_questions": section_count,
            "section_question_upload_seconds": round(section_question_upload_seconds, 4),
            "section_question_insight_seconds": round(section_insight_seconds, 4),
            "correctness": "upload, query, edit, attempt, review, and deletion assertions passed",
            "limitations": "Signature-valid deterministic payloads approximate image sizes; pixels are not decoded or AI analyzed.",
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
            "last_result_count": len(result) if isinstance(result, list) else result["total_questions"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    asyncio.run(run(args.count, args.repeats, args.json_output))
