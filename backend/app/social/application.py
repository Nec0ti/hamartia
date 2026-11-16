"""Factory for the isolated social-only ASGI application."""

from fastapi import FastAPI

from app.social.api import create_router
from app.social.security import Verifier


def create_social_app(project_id: str, verifier: Verifier) -> FastAPI:
    if not project_id or project_id.strip() != project_id:
        raise ValueError("FIREBASE_PROJECT_ID must be configured")
    app = FastAPI(title="Hamartia Social Prototype", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_router(project_id, verifier))
    return app
