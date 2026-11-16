"""Hamartia FastAPI application entrypoint.

Wires every router behind a single CORS-enabled app. The datastore path is
resolved from core.config so the service and routers share one location.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import backup, clock, cosmos, exam_profiles, exams, learning_evidence, practice, questions, settings, student_profile, study_agent
from app.core.config import DATA_DIR
from app.core.http_errors import safe_validation_error_handler
from app.services.data_lock import DataDirectoryLock


@asynccontextmanager
async def lifespan(app: FastAPI):
    with DataDirectoryLock(DATA_DIR):
        yield


app = FastAPI(
    title="Hamartia API",
    description="AI-powered exam diagnostics, mistake tracker, and gamified mastery platform.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_exception_handler(RequestValidationError, safe_validation_error_handler)

# CORS for the single-page React frontend (adjust origins in prod).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Order matters: more specific routes must be registered before broader ones.
app.include_router(exams.router)
app.include_router(exam_profiles.router)
app.include_router(practice.router)
app.include_router(learning_evidence.router)
app.include_router(clock.router)
app.include_router(student_profile.router)
app.include_router(questions.router)
# 'user' is imported via __import__: the name shadows a Python stdlib module,
# which breaks a plain `from app.api import user`.
app.include_router(__import__("app.api.user", fromlist=["router"]).router)
app.include_router(cosmos.router)
app.include_router(settings.router)
app.include_router(study_agent.router)
app.include_router(backup.router)

app.include_router(__import__("app.api.healthcheck", fromlist=["router"]).router)
