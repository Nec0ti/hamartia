"""AI-free mocked oracle and request-cost benchmark for the social boundary."""

import json
import socket
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.social.application import create_social_app
from app.social.security import FirebaseTokenVerifier


PROJECT = "hamartia-benchmark-project"
CLAIMS = {
    "aud": PROJECT,
    "iss": f"https://securetoken.google.com/{PROJECT}",
    "sub": "benchmark-user-001",
    "email": "must-not-leak@example.invalid",
    "name": "must-not-leak",
}


class MockVerifier:
    def __call__(self, token):
        if token == "verified":
            return CLAIMS
        if token in {"expired", "revoked", "signature-invalid"}:
            raise ValueError("mock invalid token")
        if token == "wrong-audience":
            return {**CLAIMS, "aud": "another-project"}
        if token == "wrong-issuer":
            return {**CLAIMS, "iss": "https://securetoken.google.com/another-project"}
        raise AssertionError(f"unexpected token reached verifier: {token}")


def forbidden(*_args, **_kwargs):
    raise AssertionError("Firebase SDK or external network must not be used by benchmark")


def main():
    expected = {
        "verified": (200, {"uid": "benchmark-user-001"}),
        "expired": (401, {"detail": "Invalid bearer token"}),
        "revoked": (401, {"detail": "Invalid bearer token"}),
        "signature-invalid": (401, {"detail": "Invalid bearer token"}),
        "wrong-audience": (401, {"detail": "Invalid bearer token"}),
        "wrong-issuer": (401, {"detail": "Invalid bearer token"}),
    }
    app = create_social_app(PROJECT, MockVerifier())
    durations = []
    with patch.object(FirebaseTokenVerifier, "__call__", forbidden), \
            patch.object(socket.socket, "connect", forbidden), \
            patch.object(socket.socket, "connect_ex", forbidden):
        with TestClient(app) as client:
            for token, oracle in expected.items():
                response = client.get("/social/me", headers={"Authorization": f"Bearer {token}"})
                actual = (response.status_code, response.json())
                if actual != oracle:
                    raise AssertionError(f"{token}: expected {oracle!r}, got {actual!r}")
                start = time.perf_counter()
                for _ in range(100):
                    response = client.get("/social/me", headers={"Authorization": f"Bearer {token}"})
                    if (response.status_code, response.json()) != oracle:
                        raise AssertionError(f"oracle changed during repeat: {token}")
                durations.append((token, (time.perf_counter() - start) * 1000 / 100))
            router = app.router.routes[0].original_router
            if {route.path for route in router.routes} != {"/social/health", "/social/me"}:
                raise AssertionError("non-social route mounted")
    print(json.dumps({"cases": len(expected), "repeats_per_case": 100,
                      "mean_request_ms": dict(durations), "firebase_calls": 0,
                      "network_calls": 0}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
