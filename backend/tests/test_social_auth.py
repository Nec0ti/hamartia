import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.social.application import create_social_app
from app.social.security import FirebaseTokenVerifier, FirebaseVerifierUnavailable, InvalidFirebaseToken


PROJECT = "hamartia-test-project"
VALID = {
    "aud": PROJECT,
    "iss": f"https://securetoken.google.com/{PROJECT}",
    "sub": "synthetic-user-123",
    "email": "must-not-be-returned@example.invalid",
}


class FakeVerifier:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def __call__(self, token):
        self.calls.append(token)
        result = self.outcomes[token]
        if isinstance(result, Exception):
            raise result
        return result


class SocialAuthTests(unittest.TestCase):
    def setUp(self):
        self.verifier = FakeVerifier({
            "valid": VALID,
            "expired": InvalidFirebaseToken("expired"),
            "revoked": InvalidFirebaseToken("revoked"),
            "outage": FirebaseVerifierUnavailable("provider unavailable"),
            "wrong-project": {**VALID, "aud": "another-project"},
            "wrong-issuer": {**VALID, "iss": "https://securetoken.google.com/another-project"},
            "empty-uid": {**VALID, "sub": ""},
            "long-uid": {**VALID, "sub": "u" * 129},
            "spaced-uid": {**VALID, "sub": " uid"},
        })
        self.client = TestClient(create_social_app(PROJECT, self.verifier))

    def test_valid_token_returns_uid_only(self):
        response = self.client.get("/social/me", headers={"Authorization": "Bearer valid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"uid": "synthetic-user-123"})

    def test_bearer_scheme_is_case_insensitive(self):
        for scheme in ("bearer", "BEARER", "bEaReR"):
            with self.subTest(scheme=scheme):
                response = self.client.get("/social/me", headers={"Authorization": f"{scheme} valid"})
                self.assertEqual(response.status_code, 200)

    def test_missing_and_malformed_tokens_are_rejected_before_verification(self):
        for header in (None, "Basic abc", "Bearer", "Bearer ", "Bearer two words"):
            headers = {} if header is None else {"Authorization": header}
            with self.subTest(header=header):
                self.assertEqual(self.client.get("/social/me", headers=headers).status_code, 401)
        self.assertEqual(self.verifier.calls, [])

    def test_expired_revoked_and_wrong_project_tokens_are_rejected(self):
        for token in ("expired", "revoked", "wrong-project"):
            with self.subTest(token=token):
                response = self.client.get("/social/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 401)

    def test_verifier_outage_returns_generic_service_unavailable(self):
        response = self.client.get("/social/me", headers={"Authorization": "Bearer outage"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Identity verification unavailable"})

    def test_issuer_and_uid_constraints_are_enforced(self):
        for token in ("wrong-issuer", "empty-uid", "long-uid", "spaced-uid"):
            with self.subTest(token=token):
                response = self.client.get("/social/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 401)

    def test_only_social_health_and_me_routes_are_mounted(self):
        router = self.client.app.router.routes[0].original_router
        paths = {route.path for route in router.routes}
        self.assertEqual(paths, {"/social/health", "/social/me"})
        self.assertEqual(self.client.get("/social/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/study-agent").status_code, 404)

    def test_entrypoint_fails_closed_before_firebase_init_without_project_id(self):
        from app.social_server import main

        with patch.dict("os.environ", {"FIREBASE_PROJECT_ID": ""}, clear=False):
            with self.assertRaisesRegex(SystemExit, "FIREBASE_PROJECT_ID is required"):
                main()

    def test_entrypoint_defaults_to_loopback_and_rejects_public_bind(self):
        from app import social_server

        with patch.dict("os.environ", {"FIREBASE_PROJECT_ID": PROJECT}, clear=True), \
                patch.object(social_server, "FirebaseTokenVerifier", return_value=self.verifier), \
                patch.object(social_server.uvicorn, "run") as run:
            social_server.main()
        self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
        with patch.dict("os.environ", {"FIREBASE_PROJECT_ID": PROJECT, "SOCIAL_HOST": "0.0.0.0"}, clear=True):
            with self.assertRaisesRegex(SystemExit, "must be loopback"):
                social_server.main()

    def test_missing_project_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            create_social_app("", self.verifier)

    def test_firebase_sdk_checks_revocation_for_configured_project(self):
        sdk_app = object()
        claims = {**VALID}
        initialize_app = Mock(return_value=sdk_app)
        verify_id_token = Mock(return_value=claims)
        class InvalidIdTokenError(Exception):
            pass

        auth = SimpleNamespace(verify_id_token=verify_id_token, InvalidIdTokenError=InvalidIdTokenError)
        firebase_admin = SimpleNamespace(initialize_app=initialize_app, auth=auth)
        with patch.dict("sys.modules", {"firebase_admin": firebase_admin,
                                         "firebase_admin.auth": auth}):
            verifier = FirebaseTokenVerifier(PROJECT)
            self.assertEqual(verifier("sample-token"), claims)
        initialize_app.assert_called_once_with(options={"projectId": PROJECT}, name="hamartia-social")
        verify_id_token.assert_called_once_with("sample-token", app=sdk_app, check_revoked=True)

    def test_firebase_sdk_errors_are_classified_without_exposing_details(self):
        from app.social.security import FirebaseVerifierUnavailable

        sdk_app = object()

        class InvalidIdTokenError(Exception):
            pass

        for sdk_error, application_error in (
            (InvalidIdTokenError("expired token"), InvalidFirebaseToken),
            (OSError("certificate service offline"), FirebaseVerifierUnavailable),
        ):
            with self.subTest(application_error=application_error.__name__):
                verify = Mock(side_effect=sdk_error)
                auth = SimpleNamespace(verify_id_token=verify, InvalidIdTokenError=InvalidIdTokenError)
                firebase_admin = SimpleNamespace(initialize_app=Mock(return_value=sdk_app), auth=auth)
                with patch.dict("sys.modules", {"firebase_admin": firebase_admin,
                                                 "firebase_admin.auth": auth}):
                    verifier = FirebaseTokenVerifier(PROJECT)
                    with self.assertRaises(application_error):
                        verifier("sample-token")


if __name__ == "__main__":
    unittest.main()
