"""Private identity and owner-scoped profile routes for the social prototype."""

from fastapi import APIRouter, Header, HTTPException, Response

from app.social.profile import Profile, ProfilePatch
from app.social.security import (
    InvalidFirebaseToken,
    Verifier,
    validate_identity,
)


def _verified_uid(authorization: str | None, project_id: str, verifier: Verifier) -> str:
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
        return validate_identity(claims, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from exc


def create_router(project_id: str, verifier: Verifier, profile_repository=None) -> APIRouter:
    router = APIRouter(prefix="/social", tags=["social"])

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.get("/me")
    def me(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        return {"uid": _verified_uid(authorization, project_id, verifier)}

    @router.get("/me/profile", response_model=Profile)
    def get_profile(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        uid = _verified_uid(authorization, project_id, verifier)
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Profile storage unavailable")
        try:
            return Profile(**(profile_repository.get_profile(uid) or {}))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Profile storage unavailable") from exc

    @router.patch("/me/profile", response_model=Profile)
    def patch_profile(body: ProfilePatch, response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        uid = _verified_uid(authorization, project_id, verifier)
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Profile storage unavailable")
        try:
            fields = body.model_dump(exclude_unset=True)
            return Profile(**(profile_repository.patch_profile(uid, fields) or {}))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Profile storage unavailable") from exc

    return router
