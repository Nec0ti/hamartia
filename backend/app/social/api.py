"""Routes for the private, data-free social authentication prototype."""

from fastapi import APIRouter, Header, HTTPException

from app.social.security import (
    FirebaseVerifierUnavailable,
    InvalidFirebaseToken,
    Verifier,
    validate_identity,
)


def create_router(project_id: str, verifier: Verifier) -> APIRouter:
    router = APIRouter(prefix="/social", tags=["social"])

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.get("/me")
    async def me(authorization: str | None = Header(default=None)):
        scheme, separator, token = authorization.partition(" ") if authorization else ("", "", "")
        if not separator or scheme.casefold() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        if not token or any(char.isspace() for char in token):
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        try:
            claims = verifier(token)
        except InvalidFirebaseToken as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Identity verification unavailable") from exc
        try:
            uid = validate_identity(claims, project_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        return {"uid": uid}

    return router
