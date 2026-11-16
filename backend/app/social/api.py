"""Routes for the private, data-free social authentication prototype."""

from fastapi import APIRouter, Header, HTTPException

from app.social.security import Verifier, validate_identity


def create_router(project_id: str, verifier: Verifier) -> APIRouter:
    router = APIRouter(prefix="/social", tags=["social"])

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.get("/me")
    async def me(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        token = authorization[7:]
        if not token or any(char.isspace() for char in token):
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        try:
            claims = verifier(token)
            uid = validate_identity(claims, project_id)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        return {"uid": uid}

    return router
