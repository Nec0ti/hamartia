"""Hamartia FastAPI application entrypoint.

Wires every router behind a single CORS-enabled app. The datastore path is
resolved from core.config so the service and routers share one location.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, cosmos, exams, questions, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Datastore is created lazily by the storage dependency; nothing to tear
    # down on shutdown.
    yield


app = FastAPI(
    title="Hamartia API",
    description="AI-powered exam diagnostics, mistake tracker, and gamified mastery platform.",
    version="1.0.0",
    lifespan=lifespan,
)

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
app.include_router(questions.router)
# 'user' is imported via __import__: the name shadows a Python stdlib module,
# which breaks a plain `from app.api import user`.
app.include_router(__import__("app.api.user", fromlist=["router"]).router)
app.include_router(cosmos.router)
app.include_router(agent.router)
app.include_router(settings.router)

app.include_router(__import__("app.api.healthcheck", fromlist=["router"]).router)
