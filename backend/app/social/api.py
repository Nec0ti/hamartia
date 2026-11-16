"""Private identity and owner-scoped profile routes for the social prototype."""

from fastapi import APIRouter, Header, HTTPException, Query, Response
from uuid import UUID

from app.social.forum import ForumPost, ForumPostCreate, ForumPostSummary, ModerationDecision
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


def create_router(project_id: str, verifier: Verifier, profile_repository=None, moderator_uids=()) -> APIRouter:
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

    @router.post("/forum/posts", response_model=ForumPostSummary, status_code=201)
    def create_forum_post(body: ForumPostCreate, response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        uid = _verified_uid(authorization, project_id, verifier)
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Forum storage unavailable")
        try:
            return profile_repository.create_forum_post(uid, body.title, body.body)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Forum storage unavailable") from exc

    @router.get("/forum/posts", response_model=list[ForumPost])
    def list_forum_posts(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        authorization: str | None = Header(default=None),
    ):
        response.headers["Cache-Control"] = "no-store"
        _verified_uid(authorization, project_id, verifier)
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Forum storage unavailable")
        try:
            return profile_repository.list_approved_forum_posts(limit)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Forum storage unavailable") from exc

    @router.get("/forum/moderation", response_model=list[ForumPost])
    def list_pending_for_moderation(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        authorization: str | None = Header(default=None),
    ):
        response.headers["Cache-Control"] = "no-store"
        uid = _verified_uid(authorization, project_id, verifier)
        if uid not in moderator_uids:
            raise HTTPException(status_code=403, detail="Moderator access required")
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Forum storage unavailable")
        try:
            return profile_repository.list_pending_forum_posts(limit, uid)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Forum storage unavailable") from exc

    @router.patch("/forum/posts/{post_id}/moderation", response_model=ForumPostSummary)
    def decide_forum_post(
        post_id: UUID,
        body: ModerationDecision,
        response: Response,
        authorization: str | None = Header(default=None),
    ):
        response.headers["Cache-Control"] = "no-store"
        uid = _verified_uid(authorization, project_id, verifier)
        if uid not in moderator_uids:
            raise HTTPException(status_code=403, detail="Moderator access required")
        if profile_repository is None:
            raise HTTPException(status_code=503, detail="Forum storage unavailable")
        try:
            result = profile_repository.moderate_forum_post(post_id, uid, body.decision)
        except ValueError as exc:
            if str(exc) == "not_found":
                raise HTTPException(status_code=404, detail="Forum post not found") from exc
            if str(exc) == "self_moderation":
                raise HTTPException(status_code=403, detail="Authors cannot moderate their own posts") from exc
            if str(exc) == "already_moderated":
                raise HTTPException(status_code=409, detail="Forum post is no longer pending") from exc
            raise HTTPException(status_code=503, detail="Forum storage unavailable") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Forum storage unavailable") from exc
        return result

    return router
