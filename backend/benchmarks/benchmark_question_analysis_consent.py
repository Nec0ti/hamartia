"""Persisted host-only question-analysis consent benchmark with a fixed mock transport."""

import argparse
import asyncio
from contextlib import ExitStack, contextmanager
import json
import socket
import statistics
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import questions, settings
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import CouncilAnalysis, Question, Settings
from app.services.ai_service import AIService
from app.services.question_analysis_consent import QuestionAnalysisConsentRegistry
from app.services.storage import StorageService
from benchmark_common import emit

ENDPOINT = "https://provider.invalid:9443/v1"
MODEL = "synthetic-consent-benchmark"
SYNTHETIC_KEY = "synthetic-only-not-a-credential"
OCR_TEXT = "Synthetic question: if 2x = 8, what is x?"
IMAGE_BYTES = b"\x89PNG\r\n\x1a\nsynthetic-benchmark-image"
VERDICT = {
    "hamartia_tag": "[Distractor Trap]",
    "root_cause": "Synthetic mocked diagnosis",
    "action_advice": "Check the operation in the final step.",
    "difficulty": 2,
    "subject_affinity": "Synthetic Mathematics",
}


def network_tripwires():
    def blocked(*_args, **_kwargs):
        raise AssertionError("non-mocked network access during host-only benchmark")

    return (
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
        patch.object(socket, "create_connection", blocked),
        patch.object(httpx.AsyncHTTPTransport, "handle_async_request", blocked),
        patch.object(httpx.HTTPTransport, "handle_request", blocked),
    )


def fixture(index):
    return Question(
        id=f"consent-bench-{index:04d}", image_name="synthetic.png", image_path="uploads/synthetic.png",
        ocr_text=OCR_TEXT, subject="Synthetic Mathematics", topic="Linear equations",
        hamartia_tag="[Knowledge Gap]", created_at="2026-11-17T12:34:56Z",
    )


def expected_disclosure():
    return {
        "endpoint_class": "remote",
        "endpoint_authority": "provider.invalid:9443",
        "scheme": "https",
        "model": MODEL,
        "payload": {
            "analysis_instructions_included": True,
            "ocr_text_included": True,
            "ocr_text_has_content": True,
            "image_filename_included": True,
            "saved_image_included": True,
        },
        "auth_setting_category": "configured_secret",
        "auth_value_category": "configured_secret",
    }


def expected_row(question):
    return {
        "id": question.id,
        "image_name": "synthetic.png",
        "image_path": "uploads/synthetic.png",
        "ocr_text": OCR_TEXT,
        "subject": "Synthetic Mathematics",
        "topic": "Linear equations",
        "curriculum_reference": {
            "framework": "", "source": "", "version": "", "grade_year": "", "unit_theme": "",
            "learning_outcome": "", "process_component": "", "source_url": "",
        },
        "analysis": {
            "counselors": {name: "" for name in (
                "dissenter", "first_principles", "expansionist", "outsider", "executor",
            )},
            "verdict": VERDICT,
            "analyzed_at": question.created_at,
        },
        "hamartia_tag": VERDICT["hamartia_tag"],
        "created_at": question.created_at,
        "reviewed_at": "",
        "review_attempts": [],
        "exam_id": "",
        "question_number": None,
        "solve_order": None,
        "time_spent_seconds": None,
        "exam_section_total": None,
    }


class MockProvider:
    def __init__(self):
        self.attempts = []
        self.lock = threading.Lock()
        self.block_entered = None
        self.release = None
        self.fail_next = False

    async def __call__(self, request):
        with self.lock:
            self.attempts.append(request)
            should_fail = self.fail_next
            self.fail_next = False
            entered, release = self.block_entered, self.release
        if str(request.url) != f"{ENDPOINT}/chat/completions":
            raise AssertionError(f"unexpected mocked URL: {request.url}")
        if request.headers.get("authorization") != f"Bearer {SYNTHETIC_KEY}":
            raise AssertionError("mock request did not use only the synthetic fixture key")
        body = json.loads(request.content)
        if body.get("model") != MODEL or OCR_TEXT not in json.dumps(body, ensure_ascii=False):
            raise AssertionError("mock request differs from the synthetic approved question snapshot")
        if should_fail:
            raise httpx.ConnectError("synthetic mocked transport failure", request=request)
        if entered is not None:
            entered.set()
            if not await asyncio.to_thread(release.wait, 10):
                raise TimeoutError("benchmark did not release suspended mock transport")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"verdict": VERDICT})}}]})


def setup_app(storage):
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
    app.include_router(questions.router)
    app.include_router(settings.router)
    app.dependency_overrides[questions.get_storage] = lambda: storage
    app.dependency_overrides[settings.get_storage] = lambda: storage
    return app


@contextmanager
def close_client(client):
    try:
        yield
    finally:
        asyncio.run(client.aclose())


def seed(storage, root, question):
    image = root / question.image_path
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(IMAGE_BYTES)
    storage.save_list("questions.json", [question])
    storage.save_doc("settings.json", Settings(
        litellm_base_url=ENDPOINT, model_name=MODEL, api_key=SYNTHETIC_KEY,
    ))


def run_trial(count):
    mock = MockProvider()
    transport = httpx.MockTransport(mock)
    original_init = AIService.__init__

    def fixed_transport_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if kwargs.get("max_retries", 0) != 0:
            raise AssertionError("question consent must keep retries disabled")
        self._http_client = client

    trips = network_tripwires()
    with tempfile.TemporaryDirectory(prefix="hamartia-question-consent-bench-") as directory:
        root = Path(directory)
        client = httpx.AsyncClient(transport=transport)
        storage = StorageService(root)
        app = setup_app(storage)
        registry_patch = patch.object(questions, "question_analysis_consents", QuestionAnalysisConsentRegistry())
        data_patch = patch.object(questions, "DATA_DIR", root)
        init_patch = patch.object(AIService, "__init__", fixed_transport_init)
        with close_client(client), registry_patch, data_patch, init_patch, ExitStack() as tripwires, TestClient(app) as api:
            for tripwire in trips:
                tripwires.enter_context(tripwire)
            seed(storage, root, fixture(0))
            before = len(mock.attempts)
            preview_response = api.post("/questions/consent-bench-0000/analysis-preview")
            if preview_response.status_code != 200 or len(mock.attempts) != before:
                raise AssertionError("preview dispatched transport or failed")
            preview = preview_response.json()
            if set(preview) != {"consent_id", *expected_disclosure()}:
                raise AssertionError("preview returned unexpected disclosure fields")
            actual_disclosure = {key: value for key, value in preview.items() if key != "consent_id"}
            if actual_disclosure != expected_disclosure() or SYNTHETIC_KEY in json.dumps(preview):
                raise AssertionError("preview disclosure differs from exact independent oracle or leaked key")
            cancelled = api.delete(f"/questions/consent-bench-0000/analysis-preview/{preview['consent_id']}")
            replay = api.post("/questions/consent-bench-0000/analyze", json={"consent_id": preview["consent_id"]})
            if cancelled.status_code != 204 or replay.status_code != 409 or len(mock.attempts) != before:
                raise AssertionError("cancel/decline or cancelled approval reached mocked transport")

            samples = []
            for index in range(count):
                question = fixture(index + 1)
                seed(storage, root, question)
                started = time.perf_counter()
                approved_preview = api.post(f"/questions/{question.id}/analysis-preview")
                if approved_preview.status_code != 200:
                    raise AssertionError("local consent preview failed")
                approved = approved_preview.json()
                if {key: value for key, value in approved.items() if key != "consent_id"} != expected_disclosure():
                    raise AssertionError("timed preview differs from exact disclosure oracle")
                response = api.post(f"/questions/{question.id}/analyze", json={"consent_id": approved["consent_id"]})
                elapsed = time.perf_counter() - started
                if response.status_code != 200:
                    raise AssertionError(f"approved synthetic analysis failed: {response.status_code}")
                actual = storage.load_list("questions.json", Question)
                if len(actual) != 1:
                    raise AssertionError("unexpected question rows after host save")
                if actual[0].model_dump() != expected_row(question):
                    raise AssertionError("persisted Question row differs from independent full-row oracle")
                if len(mock.attempts) != before + index + 1:
                    raise AssertionError("approved request did not make exactly one mocked attempt")
                samples.append(elapsed)
                duplicate = api.post(f"/questions/{question.id}/analyze", json={"consent_id": approved["consent_id"]})
                if duplicate.status_code != 409 or len(mock.attempts) != before + index + 1:
                    raise AssertionError("approval replay was not rejected before transport")
            timed = {
                "samples": len(samples),
                "p50_seconds": round(statistics.median(samples), 6),
                "p95_seconds": round(sorted(samples)[max(0, (len(samples) * 95 + 99) // 100 - 1)], 6),
            }

            # Correctness-only probes run after timing so waits and failures do not skew samples.
            stale_question = fixture(9001)
            seed(storage, root, stale_question)
            stale = api.post(f"/questions/{stale_question.id}/analysis-preview").json()
            edited = api.patch(f"/questions/{stale_question.id}", json={
                "subject": "Synthetic Mathematics", "topic": "Changed", "ocr_text": "Synthetic prompt B",
            })
            attempts = len(mock.attempts)
            stale_dispatch = api.post(f"/questions/{stale_question.id}/analyze", json={"consent_id": stale["consent_id"]})
            [stale_saved] = storage.load_list("questions.json", Question)
            if edited.status_code != 200 or stale_dispatch.status_code != 409 or len(mock.attempts) != attempts:
                raise AssertionError("stale-before-dispatch consent was not rejected without transport")
            if stale_saved.ocr_text != "Synthetic prompt B" or stale_saved.analysis is not None:
                raise AssertionError("stale dispatch clobbered the edited question")
            settings_question = fixture(9006)
            seed(storage, root, settings_question)
            settings_preview = api.post(f"/questions/{settings_question.id}/analysis-preview").json()
            changed_settings = api.patch("/settings", json={
                "litellm_base_url": ENDPOINT, "model_name": "changed-synthetic-model",
            })
            attempts = len(mock.attempts)
            stale_settings = api.post(f"/questions/{settings_question.id}/analyze", json={
                "consent_id": settings_preview["consent_id"],
            })
            [settings_saved] = storage.load_list("questions.json", Question)
            if changed_settings.status_code != 200 or stale_settings.status_code != 409 or len(mock.attempts) != attempts:
                raise AssertionError("stale settings approval was not rejected before transport")
            saved_settings = storage.load_doc("settings.json", Settings)
            if settings_saved.model_dump() != settings_question.model_dump() or saved_settings.model_name != "changed-synthetic-model":
                raise AssertionError("stale settings check changed stored question or reverted settings")

            race_results = []
            for setting_race in (False, True):
                question = fixture(9002 if setting_race else 9003)
                seed(storage, root, question)
                preview = api.post(f"/questions/{question.id}/analysis-preview").json()
                mock.block_entered = threading.Event()
                mock.release = threading.Event()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(api.post, f"/questions/{question.id}/analyze", json={"consent_id": preview["consent_id"]})
                    if not mock.block_entered.wait(10):
                        raise AssertionError("approved request did not enter suspended MockTransport")
                    if setting_race:
                        changed = api.patch("/settings", json={"litellm_base_url": "https://provider.invalid:9443/v1", "model_name": "changed-synthetic-model"})
                    else:
                        changed = api.patch(f"/questions/{question.id}", json={
                            "subject": "Synthetic Mathematics", "topic": "Changed during request", "ocr_text": "Synthetic prompt C",
                        })
                    mock.release.set()
                    response = pending.result(timeout=15)
                mock.block_entered = mock.release = None
                [stored] = storage.load_list("questions.json", Question)
                if changed.status_code != 200 or response.status_code != 409 or stored.analysis is not None:
                    raise AssertionError("in-flight stale response did not conflict without analysis persistence")
                if setting_race:
                    saved_settings = storage.load_doc("settings.json", Settings)
                    if (saved_settings.model_name, stored.ocr_text) != ("changed-synthetic-model", question.ocr_text):
                        raise AssertionError("settings race clobbered the latest setting or question")
                elif (stored.ocr_text, stored.topic) != ("Synthetic prompt C", "Changed during request"):
                    raise AssertionError("question race clobbered the latest question edit")
                race_results.append("settings" if setting_race else "question")

            tag_question = fixture(9004)
            seed(storage, root, tag_question)
            preview = api.post(f"/questions/{tag_question.id}/analysis-preview").json()
            mock.block_entered = threading.Event()
            mock.release = threading.Event()
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(api.post, f"/questions/{tag_question.id}/analyze", json={"consent_id": preview["consent_id"]})
                if not mock.block_entered.wait(10):
                    raise AssertionError("manual-tag probe did not reach MockTransport")
                changed = api.patch(f"/questions/{tag_question.id}/tag", json={"hamartia_tag": "[Reading Slip]"})
                mock.release.set()
                response = pending.result(timeout=15)
            mock.block_entered = mock.release = None
            [tag_saved] = storage.load_list("questions.json", Question)
            if changed.status_code != 200 or response.status_code != 200 or tag_saved.hamartia_tag != "[Reading Slip]":
                raise AssertionError("successful analysis did not preserve the latest manual tag")
            manual_tag_expected = expected_row(tag_question)
            manual_tag_expected["hamartia_tag"] = "[Reading Slip]"
            if tag_saved.model_dump() != manual_tag_expected:
                raise AssertionError("manual-tag success differs from independent full-row oracle")

            failure_question = fixture(9005)
            seed(storage, root, failure_question)
            failure_preview = api.post(f"/questions/{failure_question.id}/analysis-preview").json()
            mock.fail_next = True
            attempts = len(mock.attempts)
            failed = api.post(f"/questions/{failure_question.id}/analyze", json={"consent_id": failure_preview["consent_id"]})
            [failure_saved] = storage.load_list("questions.json", Question)
            if failed.status_code != 502 or len(mock.attempts) != attempts + 1 or failure_saved.analysis is not None:
                raise AssertionError("mock transport failure retried or changed persisted question")

            output = {
                "benchmark": "question_analysis_consent",
                "timed_operation": "persisted local preview + one-use approval + synthetic fixed MockTransport response + Question save",
                "timing": timed,
                "correctness_probes": {
                    "preview_cancel_replay_zero_transport": True,
                    "exact_preview_disclosure_and_key_omission": True,
                    "one_use_approval_and_full_persisted_row": True,
                    "stale_question_and_settings_before_dispatch_zero_transport": True,
                    "in_flight_stale_conflicts_without_clobber": race_results,
                    "manual_tag_preserved_after_success": True,
                    "failure_one_mocked_attempt_no_retry": True,
                    "mocked_transport_attempts": len(mock.attempts),
                },
                "transport": "fixed httpx.MockTransport only",
                "provider_or_model_execution": False,
                "network_access": False,
            }
            return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--samples-per-repeat", type=int, default=8)
    args = parser.parse_args()
    if args.repeats < 1 or args.samples_per_repeat < 1:
        parser.error("repeats and samples-per-repeat must be positive")
    repeats = [run_trial(args.samples_per_repeat) for _ in range(args.repeats)]
    emit({
        "benchmark": "question_analysis_consent",
        "repeats": repeats,
        "samples_per_repeat": args.samples_per_repeat,
        "provider_or_model_execution": False,
        "network_access": False,
    })


if __name__ == "__main__":
    main()
