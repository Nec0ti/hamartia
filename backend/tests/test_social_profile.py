import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from benchmarks.benchmark_social_profiles import percentile
from app.social.application import create_social_app
from app.social.database import PostgresProfileRepository, migrate_social_database
from app.social.profile import Profile, ProfilePatch, public_profile_projection
from app.social.security import InvalidFirebaseToken


PROJECT = "hamartia-social-profile-test"
TEST_DATABASE_URL = os.environ.get("HAMARTIA_SOCIAL_TEST_DATABASE_URL")


class ProfileModelTests(unittest.TestCase):
    def test_benchmark_percentiles_use_nearest_rank_at_small_sample_sizes(self):
        samples = list(range(1, 25))
        self.assertEqual(percentile(samples, 0.50), 12)
        self.assertEqual(percentile(samples, 0.95), 23)
        self.assertEqual(percentile(samples, 0.99), 24)

    def test_private_defaults_and_allowlisted_projection(self):
        profile = Profile(
            nickname="Visible name", nickname_public=True,
            age=18, age_public=False,
            avatar_preset="leaf", avatar_preset_public=True,
        )
        self.assertEqual(
            public_profile_projection({**profile.model_dump(), "uid": "never-project", "email": "never-project"}),
            {"nickname": "Visible name", "avatar_preset": "leaf"},
        )
        self.assertTrue(all(not getattr(Profile(), f"{field}_public") for field in (
            "nickname", "age", "school_grade", "school_class", "curriculum",
            "study_preferences", "study_goals", "avatar_preset",
        )))

    def test_patch_rejects_mass_assignment_unknown_fields_and_invalid_values(self):
        for data in (
            {"uid": "attacker"},
            {"email": "claimed@example.invalid"},
            {"gender": "not-collected"},
            {"birth_date": "2008-01-01"},
            {"avatar_preset": "https://example.invalid/avatar.png"},
            {"age": "17"},
            {"age": True},
            {"age": 4},
            {"age": 121},
            {"nickname": "bad\u0000text"},
            {"nickname": "\ud800"},
            {"nickname": "x" * 81},
        ):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    ProfilePatch.model_validate(data)

    def test_database_failure_is_generic_and_does_not_leak_connection_details(self):
        class BrokenRepository:
            def open(self):
                pass

            def close(self):
                pass

            def get_profile(self, _uid):
                raise RuntimeError("postgresql://operator:secret@db.invalid/private")

        claims = {"aud": PROJECT, "iss": f"https://securetoken.google.com/{PROJECT}", "sub": "user-a"}
        with TestClient(create_social_app(PROJECT, lambda _token: claims, BrokenRepository())) as client:
            response = client.get("/social/me/profile", headers={"Authorization": "Bearer valid"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Profile storage unavailable"})
        self.assertNotIn("secret", response.text)

    def test_invalid_tokens_are_rejected_before_profile_storage_is_touched(self):
        class TripwireRepository:
            def __init__(self):
                self.calls = 0

            def open(self):
                pass

            def close(self):
                pass

            def get_profile(self, _uid):
                self.calls += 1
                raise AssertionError("invalid identity reached profile storage")

            def patch_profile(self, _uid, _changes):
                self.calls += 1
                raise AssertionError("invalid identity reached profile storage")

        repository = TripwireRepository()

        def verifier(_token):
            raise InvalidFirebaseToken("invalid test token")

        with TestClient(create_social_app(PROJECT, verifier, repository)) as client:
            headers = {"Authorization": "Bearer invalid"}
            read = client.get("/social/me/profile", headers=headers)
            write = client.patch("/social/me/profile", headers=headers, json={"nickname": "must not persist"})
        self.assertEqual(read.status_code, 401)
        self.assertEqual(write.status_code, 401)
        self.assertEqual(repository.calls, 0)


@unittest.skipUnless(TEST_DATABASE_URL, "requires a dedicated real PostgreSQL test database")
class PostgresSocialProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.psycopg = psycopg
        migrate_social_database(TEST_DATABASE_URL)
        migrate_social_database(TEST_DATABASE_URL)

    def setUp(self):
        suffix = uuid4().hex
        self.uid_a = f"test-a-{suffix}"
        self.uid_b = f"test-b-{suffix}"
        self.test_uids = [self.uid_a, self.uid_b]
        self.tokens = {"token-a": self.uid_a, "token-b": self.uid_b}

        def verifier(token):
            if token == "verifier-outage":
                raise RuntimeError("mock verifier credentials must not leak")
            if token == "invalid-token":
                raise InvalidFirebaseToken("mock invalid token details must not leak")
            uid = self.tokens.get(token)
            if uid is None:
                raise InvalidFirebaseToken("unknown token")
            return {
                "aud": PROJECT,
                "iss": f"https://securetoken.google.com/{PROJECT}",
                "sub": uid,
                "email": "private-claim@example.invalid",
            }

        self.repository = PostgresProfileRepository(TEST_DATABASE_URL, max_connections=10)
        self.app = create_social_app(PROJECT, verifier, self.repository)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        with self.psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute("DELETE FROM social_profiles WHERE uid = ANY(%s)", (self.test_uids,))

    def request(self, token, method="get", body=None):
        kwargs = {"headers": {"Authorization": f"Bearer {token}"}}
        if body is not None:
            kwargs["json"] = body
        return getattr(self.client, method)("/social/me/profile", **kwargs)

    def test_get_defaults_and_two_users_are_owner_scoped(self):
        defaults = self.request("token-a").json()
        self.assertEqual(self.request("token-a").headers["cache-control"], "no-store")
        self.assertEqual(defaults["nickname"], None)
        self.assertEqual(defaults["age"], None)
        self.assertFalse(any(key.endswith("_public") and value for key, value in defaults.items()))

        response_a = self.request("token-a", "patch", {
            "nickname": "Student A", "age": 17, "school_grade": "11",
            "study_goals": "Finish the electricity unit", "nickname_public": True,
        })
        response_b = self.request("token-b", "patch", {
            "nickname": "Student B", "curriculum": "User-entered path",
        })
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        profile_a = self.request("token-a").json()
        profile_b = self.request("token-b").json()
        self.assertEqual(profile_a["nickname"], "Student A")
        self.assertEqual(profile_a["age"], 17)
        self.assertIsNone(profile_a["curriculum"])
        self.assertEqual(profile_b["nickname"], "Student B")
        self.assertEqual(profile_b["curriculum"], "User-entered path")
        self.assertIsNone(profile_b["age"])
        self.assertNotIn("uid", profile_a)
        self.assertNotIn("email", profile_a)
        self.assertNotIn("private-claim@example.invalid", response_a.text)

        injected_uid = self.request("token-b", "patch", {"uid": self.uid_a, "nickname": "Injected"})
        self.assertEqual(injected_uid.status_code, 422)
        self.assertEqual(self.request("token-a").json()["nickname"], "Student A")

    def test_concurrent_partial_creates_merge_without_lost_fields(self):
        cases = [
            ("nickname", "Concurrent student"),
            ("age", 20),
            ("school_grade", "adult learner"),
            ("school_class", "evening"),
            ("curriculum", "self-directed"),
            ("study_preferences", "short sessions"),
            ("study_goals", "review algebra"),
            ("avatar_preset", "lantern"),
        ]
        self.tokens["token-c"] = f"test-c-{uuid4().hex}"
        self.test_uids.append(self.tokens["token-c"])

        def patch_one(item):
            key, value = item
            response = self.request("token-c", "patch", {key: value})
            return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(patch_one, cases))
        self.assertTrue(all(status == 200 for status, _ in responses))
        complete = self.request("token-c").json()
        for key, expected in cases:
            self.assertEqual(complete[key], expected)

    def test_invalid_verifier_failures_are_generic(self):
        invalid = self.request("invalid-token")
        outage = self.request("verifier-outage")
        self.assertEqual((invalid.status_code, invalid.json()), (401, {"detail": "Invalid bearer token"}))
        self.assertEqual(outage.status_code, 503)
        self.assertEqual(outage.json(), {"detail": "Identity verification unavailable"})
        self.assertNotIn("mock", invalid.text + outage.text)
        self.assertNotIn("private-claim@example.invalid", invalid.text + outage.text)

    def test_unknown_and_invalid_profile_values_do_not_persist(self):
        for body in (
            {"uid": self.uid_b, "nickname": "owner injection"},
            {"email": "claimed@example.invalid"},
            {"gender": "x"},
            {"birth_date": "2008-02-03"},
            {"avatar_preset": "https://example.invalid/a.png"},
            {"age": "17"},
            {"age": 4},
            {"nickname": "bad\u0000text"},
        ):
            response = self.request("token-a", "patch", body)
            self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.request("token-a").json()["nickname"])

    def test_profile_endpoints_are_private_and_projection_is_not_mounted(self):
        paths = {route.path for route in self.app.router.routes[0].original_router.routes}
        self.assertEqual(paths, {
            "/social/health", "/social/me", "/social/me/profile",
            "/social/forum/posts", "/social/forum/moderation",
            "/social/forum/posts/{post_id}/moderation",
        })
        self.assertEqual(self.client.get("/social/profiles/anyone").status_code, 404)
        self.assertEqual(self.client.get("/social/me/profile").status_code, 401)


if __name__ == "__main__":
    unittest.main()
