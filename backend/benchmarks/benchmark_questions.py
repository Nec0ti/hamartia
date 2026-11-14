"""Measure local question-image storage and tagging without calling a model."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api import questions
from app.models.schemas import Question
from app.services.storage import StorageService


def make_upload(index):
    file = tempfile.SpooledTemporaryFile()
    file.write(b"local image fixture" * 128)
    file.seek(0)
    return UploadFile(
        filename=f"question-{index}.png",
        file=file,
        headers=Headers({"content-type": "image/png"}),
    )


async def run(count=100):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        storage = StorageService(root)
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

            started = time.perf_counter()
            insights = await questions.question_insights(storage)
            insight_seconds = time.perf_counter() - started
            assert insights["total_questions"] == count
            assert insights["topics"][0]["question_count"] == count

            image = await questions.get_question_image(saved[0].id, storage)
            assert Path(image.path).is_file()
            await questions.tag_question(saved[0].id, questions.TagRequest(hamartia_tag="[Reading Slip]"), storage)

        print(json.dumps({
            "benchmark": "local_question_flow",
            "questions": count,
            "upload_seconds": round(upload_seconds, 4),
            "uploads_per_second": round(count / upload_seconds, 2),
            "list_seconds": round(list_seconds, 4),
            "insight_seconds": round(insight_seconds, 4),
            "ai_included": False,
        }))


if __name__ == "__main__":
    asyncio.run(run())
