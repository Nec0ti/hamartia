import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.social.application import create_social_app
from app.social.database import PostgresProfileRepository, migrate_social_database
from app.social.forum import ForumPostCreate, ModerationDecision
from app.social.security import InvalidFirebaseToken


PROJECT = "hamartia-social-forum-test"
TEST_DATABASE_URL = os.environ.get("HAMARTIA_SOCIAL_TEST_DATABASE_URL")


class ForumModelTests(unittest.TestCase):
    def test_post_and_decision_models_reject_identity_role_state_and_unknown_fields(self):
        for data in (
            {"title": "Title", "body": "Body", "uid": "attacker"},
            {"title": "Title", "body": "Body", "author_uid": "attacker"},
            {"title": "Title", "body": "Body", "role": "moderator"},
            {"title": "Title", "body": "Body", "status": "approved"},
            {"title": "Title", "body": "Body", "moderator_uid": "attacker"},
            {"title": " ", "body": "Body"},
            {"title": "Title", "body": "\u0000"},
            {"title": "x" * 121, "body": "Body"},
            {"title": "Title", "body": "x" * 5001},
        ):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    ForumPostCreate.model_validate(data)
        for data in ({"decision": "pending"}, {"decision": "approved", "role": "admin"}, {"status": "approved"}):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    ModerationDecision.model_validate(data)


@unittest.skipUnless(TEST_DATABASE_URL, "requires a dedicated real PostgreSQL test database")
class PostgresSocialForumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.psycopg = psycopg
        migrate_social_database(TEST_DATABASE_URL)
        migrate_social_database(TEST_DATABASE_URL)

    def setUp(self):
        suffix = uuid4().hex
        self.author = f"forum-author-{suffix}"
        self.other = f"forum-other-{suffix}"
        self.moderator = f"forum-mod-{suffix}"
        self.tokens = {
            "author-token": self.author,
            "other-token": self.other,
            "moderator-token": self.moderator,
        }

        def verifier(token):
            if token == "invalid-token":
                raise InvalidFirebaseToken("synthetic invalid token")
            uid = self.tokens.get(token)
            if uid is None:
                raise InvalidFirebaseToken("unknown synthetic token")
            return {"aud": PROJECT, "iss": f"https://securetoken.google.com/{PROJECT}", "sub": uid}

        self.repository = PostgresProfileRepository(TEST_DATABASE_URL, max_connections=10)
        self.app = create_social_app(PROJECT, verifier, self.repository, (self.moderator,))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.post_ids = []

    def tearDown(self):
        self.client.__exit__(None, None, None)
        with self.psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute("DELETE FROM social_forum_posts WHERE post_id = ANY(%s)", (self.post_ids,))

    def request(self, token, method="get", path="/social/forum/posts", body=None, **kwargs):
        options = {"headers": {"Authorization": f"Bearer {token}"}, **kwargs}
        if body is not None:
            options["json"] = body
        return getattr(self.client, method)(path, **options)

    def submit(self, token="author-token", title="Question", body="How do I approach this topic?"):
        response = self.request(token, "post", body={"title": title, "body": body})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.post_ids.append(UUID(response.json()["post_id"]))
        return response.json()

    def moderate(self, post_id, decision="approved", token="moderator-token"):
        return self.request(
            token, "patch", f"/social/forum/posts/{post_id}/moderation", {"decision": decision}
        )

    def test_submission_waits_for_moderation_and_only_approved_posts_are_readable(self):
        pending = self.submit(body="pending-secret-synthetic")
        self.assertEqual(pending["status"], "pending")
        self.assertNotIn("author_uid", pending)
        self.assertNotIn("uid", pending)
        self.assertNotIn("moderator_uid", pending)
        self.assertEqual(self.request("other-token").json(), [])

        denied_queue = self.request("other-token", path="/social/forum/moderation")
        self.assertEqual(denied_queue.status_code, 403)
        own_approval = self.moderate(pending["post_id"], token="author-token")
        self.assertEqual(own_approval.status_code, 403)
        own_rejection = self.moderate(pending["post_id"], "rejected", token="author-token")
        self.assertEqual(own_rejection.status_code, 403)

        moderators_own_post = self.submit(token="moderator-token", title="Moderator's post", body="private-to-author")
        self.assertNotIn(moderators_own_post["post_id"], [row["post_id"] for row in self.request("moderator-token", path="/social/forum/moderation").json()])
        self.assertEqual(self.moderate(moderators_own_post["post_id"], token="moderator-token").status_code, 403)

        queue = self.request("moderator-token", path="/social/forum/moderation")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.headers["cache-control"], "no-store")
        self.assertEqual(queue.json()[0]["post_id"], pending["post_id"])
        self.assertNotIn(self.author, queue.text)
        approved = self.moderate(pending["post_id"])
        self.assertEqual((approved.status_code, approved.json()["status"]), (200, "approved"))
        feed = self.request("other-token")
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.headers["cache-control"], "no-store")
        self.assertEqual([item["post_id"] for item in feed.json()], [pending["post_id"]])
        self.assertNotIn(self.author, feed.text)

        rejected = self.submit(title="Rejected", body="rejected-secret-synthetic")
        self.assertEqual(self.moderate(rejected["post_id"], "rejected").json()["status"], "rejected")
        self.assertNotIn("rejected-secret-synthetic", self.request("other-token").text)
        self.assertNotIn("rejected-secret-synthetic", self.request("moderator-token", path="/social/forum/moderation").text)

    def test_spoofed_identity_role_and_approval_fields_are_rejected_before_write(self):
        for body in (
            {"title": "Injected", "body": "test", "uid": self.other},
            {"title": "Injected", "body": "test", "author_uid": self.other},
            {"title": "Injected", "body": "test", "role": "moderator"},
            {"title": "Injected", "body": "test", "status": "approved"},
            {"title": "Injected", "body": "test", "moderator_uid": self.moderator},
        ):
            response = self.request("author-token", "post", body=body)
            self.assertEqual(response.status_code, 422)
        invalid = self.request("invalid-token", "post", body={"title": "Title", "body": "Body"})
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(self.request("other-token").json(), [])

    def test_concurrent_decisions_have_one_winner_and_pending_to_final_is_one_way(self):
        post = self.submit()

        def decide(decision):
            response = self.moderate(post["post_id"], decision)
            return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(decide, ("approved", "rejected")))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        with self.psycopg.connect(TEST_DATABASE_URL) as connection:
            final_status = connection.execute(
                "SELECT status FROM social_forum_posts WHERE post_id = %s", (UUID(post["post_id"]),)
            ).fetchone()[0]
        winning_status = results[0][1]["status"] if results[0][0] == 200 else results[1][1]["status"]
        self.assertEqual(final_status, winning_status)
        self.assertIn(final_status, {"approved", "rejected"})
        retry = self.moderate(post["post_id"], "approved")
        self.assertEqual(retry.status_code, 409)

    def test_limit_is_bounded_and_non_moderator_cannot_read_queue(self):
        self.assertEqual(self.request("other-token", path="/social/forum/posts?limit=0").status_code, 422)
        self.assertEqual(self.request("other-token", path="/social/forum/posts?limit=101").status_code, 422)
        self.assertEqual(self.request("moderator-token", path="/social/forum/moderation?limit=101").status_code, 422)
