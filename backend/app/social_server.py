"""Opt-in entrypoint for the separate social-only prototype service."""

import ipaddress
import os

import uvicorn

from app.social.application import create_social_app
from app.social.database import PostgresProfileRepository, migrate_social_database
from app.social.security import FirebaseTokenVerifier


def main() -> None:
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    if not project_id or project_id.strip() != project_id:
        raise SystemExit("FIREBASE_PROJECT_ID is required; social service was not started")
    database_url = os.environ.get("SOCIAL_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("SOCIAL_DATABASE_URL is required; social service was not started")
    host = os.environ.get("SOCIAL_HOST", "127.0.0.1")
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("not loopback")
    except ValueError as exc:
        raise SystemExit("SOCIAL_HOST must be a numeric loopback IP for this prototype") from exc
    try:
        port = int(os.environ.get("SOCIAL_PORT", "8765"))
    except ValueError as exc:
        raise SystemExit("SOCIAL_PORT must be an integer from 1 to 65535") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("SOCIAL_PORT must be an integer from 1 to 65535")
    verifier = FirebaseTokenVerifier(project_id)
    try:
        migrate_social_database(database_url)
    except Exception:
        raise SystemExit("Social database initialization failed; details omitted") from None
    repository = PostgresProfileRepository(database_url)
    uvicorn.run(create_social_app(project_id, verifier, repository), host=host, port=port)


if __name__ == "__main__":
    main()
