"""Firebase ID-token verification for the isolated social API."""

from collections.abc import Callable, Mapping


class InvalidFirebaseToken(Exception):
    """The supplied Firebase ID token is invalid, expired, or revoked."""


class FirebaseVerifierUnavailable(Exception):
    """Firebase verification could not complete because its service is unavailable."""


class FirebaseTokenVerifier:
    def __init__(self, project_id: str):
        if not project_id or project_id.strip() != project_id:
            raise ValueError("FIREBASE_PROJECT_ID must be configured")
        import firebase_admin

        self.project_id = project_id
        self.app = firebase_admin.initialize_app(options={"projectId": project_id}, name="hamartia-social")

    def __call__(self, token: str) -> Mapping[str, object]:
        from firebase_admin import auth

        try:
            return auth.verify_id_token(token, app=self.app, check_revoked=True)
        except (auth.InvalidIdTokenError, auth.UserDisabledError) as exc:
            raise InvalidFirebaseToken from exc
        except Exception as exc:
            raise FirebaseVerifierUnavailable from exc


def validate_identity(claims: Mapping[str, object], project_id: str) -> str:
    """Return only a Firebase UID after enforcing project and issuer binding."""
    if claims.get("aud") != project_id:
        raise ValueError("Invalid audience")
    if claims.get("iss") != f"https://securetoken.google.com/{project_id}":
        raise ValueError("Invalid issuer")
    uid = claims.get("sub")
    if not isinstance(uid, str) or not uid or uid.strip() != uid or len(uid) > 128:
        raise ValueError("Invalid UID")
    return uid


Verifier = Callable[[str], Mapping[str, object]]
