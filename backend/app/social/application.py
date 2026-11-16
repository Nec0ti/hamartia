"""Factory for the isolated social-only ASGI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.http_errors import safe_validation_error_handler
from app.social.api import create_router
from app.social.security import Verifier


def create_social_app(project_id: str, verifier: Verifier, profile_repository=None, moderator_uids=()) -> FastAPI:
    if not project_id or project_id.strip() != project_id:
        raise ValueError("FIREBASE_PROJECT_ID must be configured")
    @asynccontextmanager
    async def lifespan(app):
        if profile_repository is not None:
            profile_repository.open()
        try:
            yield
        finally:
            if profile_repository is not None:
                profile_repository.close()

    app = FastAPI(title="Hamartia Social Prototype", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
    app.include_router(create_router(project_id, verifier, profile_repository, frozenset(moderator_uids)))
    return app
