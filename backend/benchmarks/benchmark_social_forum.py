"""Offline PostgreSQL forum correctness and API throughput benchmark."""

import ipaddress
import json
import math
import os
import socket
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.social.application import create_social_app
from app.social.database import PostgresProfileRepository, migrate_social_database
from app.social.security import FirebaseTokenVerifier


PROJECT = "hamartia-social-forum-benchmark"
ROWS = 64
CONCURRENT_ROWS = 24
MODERATOR = "forum-bench-moderator"


class BenchmarkVerifier:
    def __call__(self, token):
        uid = (
            f"forum-bench-author-{token.removeprefix('author-token-')}"
            if token.startswith("author-token-") and token.removeprefix("author-token-").isdigit()
            else {"reader-token": "forum-bench-reader", "moderator-token": MODERATOR,
                  "rate-limit-token": "forum-bench-rate-limit-author"}.get(token)
        )
        if uid is None:
            raise AssertionError("unexpected benchmark identity")
        return {"aud": PROJECT, "iss": f"https://securetoken.google.com/{PROJECT}", "sub": uid}


def percentile(samples, probability):
    ordered = sorted(samples)
    return round(ordered[max(0, math.ceil(probability * len(ordered)) - 1)], 3)


def postgres_port(database_url):
    parsed = urlsplit(database_url)
    try:
        if not parsed.hostname or not ipaddress.ip_address(parsed.hostname).is_loopback:
            raise ValueError
        return parsed.port or 5432
    except ValueError as exc:
        raise SystemExit("benchmark database must use a numeric loopback PostgreSQL host") from exc


def guarded_connect(original, allowed_port):
    def connect(sock, address):
        try:
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback and address[1] == allowed_port:
                return original(sock, address)
        except (ValueError, IndexError):
            pass
        raise AssertionError("unexpected non-PostgreSQL network connection")
    return connect


def main():
    database_url = os.environ.get("HAMARTIA_SOCIAL_BENCHMARK_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("HAMARTIA_SOCIAL_BENCHMARK_DATABASE_URL must use PostgreSQL")
    allowed_port = postgres_port(database_url)
    import psycopg

    migrate_social_database(database_url)
    with psycopg.connect(database_url) as connection:
        server_version = connection.execute("SHOW server_version").fetchone()[0]
    run_id = uuid4().hex
    repository = PostgresProfileRepository(database_url, max_connections=8)
    app = create_social_app(PROJECT, BenchmarkVerifier(), repository, (MODERATOR,))
    created = []
    create_ms = []
    moderation_ms = []
    read_ms = []
    concurrent_ms = []
    rate_limited_ms = []
    rate_limited_posts = []
    with patch.object(FirebaseTokenVerifier, "__call__", side_effect=AssertionError("Firebase forbidden")), \
            patch.object(socket.socket, "connect", guarded_connect(socket.socket.connect, allowed_port)), \
            patch.object(socket.socket, "connect_ex", guarded_connect(socket.socket.connect_ex, allowed_port)), \
            TestClient(app) as client:
        try:
            for index in range(ROWS):
                title = f"Synthetic forum question {run_id}-{index:03d}"
                body = f"Synthetic body {run_id}-{index:03d}"
                started = time.perf_counter_ns()
                author_token = f"author-token-{index // 5}"
                response = client.post("/social/forum/posts", headers={"Authorization": f"Bearer {author_token}"}, json={"title": title, "body": body})
                create_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                if response.status_code != 201 or response.json().get("status") != "pending":
                    raise AssertionError("submission oracle mismatch")
                if "author_uid" in response.text or title in response.text or body in response.text:
                    raise AssertionError("pending content or author leaked from submission response")
                created.append((UUID(response.json()["post_id"]), title, body))

            queue = client.get("/social/forum/moderation?limit=100", headers={"Authorization": "Bearer moderator-token"})
            if queue.status_code != 200 or len(queue.json()) != ROWS:
                raise AssertionError("moderation queue oracle mismatch")
            if any("author_uid" in row or "moderator_uid" in row for row in queue.json()):
                raise AssertionError("internal identity leaked in moderation queue")

            for index, (post_id, _title, _body) in enumerate(created):
                decision = "approved" if index % 2 == 0 else "rejected"
                started = time.perf_counter_ns()
                response = client.patch(
                    f"/social/forum/posts/{post_id}/moderation",
                    headers={"Authorization": "Bearer moderator-token"},
                    json={"decision": decision},
                )
                moderation_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                if response.status_code != 200 or response.json().get("status") != decision:
                    raise AssertionError("moderation oracle mismatch")

            expected = {str(post_id): (title, body) for index, (post_id, title, body) in enumerate(created) if index % 2 == 0}
            for _ in range(ROWS):
                started = time.perf_counter_ns()
                response = client.get("/social/forum/posts?limit=100", headers={"Authorization": "Bearer reader-token"})
                read_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                if response.status_code != 200:
                    raise AssertionError("approved feed request failed")
                actual = {row["post_id"]: (row["title"], row["body"]) for row in response.json()}
                if actual != expected:
                    raise AssertionError("approved-only feed oracle mismatch")
                if "forum-bench-author" in response.text:
                    raise AssertionError("author identity leaked from feed")

            concurrent_posts = []
            for index in range(CONCURRENT_ROWS):
                title = f"Concurrent synthetic question {run_id}-{index:03d}"
                author_token = f"author-token-{100 + index // 5}"
                response = client.post("/social/forum/posts", headers={"Authorization": f"Bearer {author_token}"}, json={"title": title, "body": f"Concurrent synthetic body {index}"})
                if response.status_code != 201 or response.json().get("status") != "pending":
                    raise AssertionError("concurrent fixture submission oracle mismatch")
                concurrent_posts.append((UUID(response.json()["post_id"]), title, f"Concurrent synthetic body {index}"))
            created.extend(concurrent_posts)

            def approve_concurrently(post):
                post_id, _title, _body = post
                started = time.perf_counter_ns()
                response = client.patch(
                    f"/social/forum/posts/{post_id}/moderation",
                    headers={"Authorization": "Bearer moderator-token"}, json={"decision": "approved"},
                )
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                if response.status_code != 200 or response.json().get("status") != "approved":
                    raise AssertionError("concurrent moderation oracle mismatch")
                return elapsed

            concurrent_started = time.perf_counter_ns()
            with ThreadPoolExecutor(max_workers=8) as executor:
                concurrent_ms.extend(executor.map(approve_concurrently, concurrent_posts))
            concurrent_total_ms = (time.perf_counter_ns() - concurrent_started) / 1_000_000
            expected.update({str(post_id): (title, body) for post_id, title, body in concurrent_posts})
            response = client.get("/social/forum/posts?limit=100", headers={"Authorization": "Bearer reader-token"})
            actual = {row["post_id"]: (row["title"], row["body"]) for row in response.json()}
            if response.status_code != 200 or actual != expected:
                raise AssertionError("concurrent approval feed oracle mismatch")

            for index in range(5):
                response = client.post(
                    "/social/forum/posts", headers={"Authorization": "Bearer rate-limit-token"},
                    json={"title": f"Rate-limit fixture {run_id}-{index}", "body": "Synthetic"},
                )
                if response.status_code != 201:
                    raise AssertionError("rate-limit allowance oracle mismatch")
                rate_limited_posts.append(UUID(response.json()["post_id"]))
            started = time.perf_counter_ns()
            response = client.post(
                "/social/forum/posts", headers={"Authorization": "Bearer rate-limit-token"},
                json={"title": f"Rate-limit overflow {run_id}", "body": "Synthetic"},
            )
            rate_limited_ms.append((time.perf_counter_ns() - started) / 1_000_000)
            detail = response.json().get("detail", {})
            if (response.status_code != 429 or response.headers.get("retry-after") != str(detail.get("retry_after_seconds"))
                    or detail.get("code") != "forum_rate_limit_exceeded"):
                raise AssertionError("rate-limit response oracle mismatch")

            with psycopg.connect(database_url) as connection:
                states = dict(connection.execute(
                    "SELECT status, count(*) FROM social_forum_posts WHERE post_id = ANY(%s) GROUP BY status",
                    ([post_id for post_id, _, _ in created],),
                ).fetchall())
            if states != {"approved": ROWS // 2 + CONCURRENT_ROWS, "rejected": ROWS // 2}:
                raise AssertionError("stored decision state oracle mismatch")
        finally:
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    "DELETE FROM social_forum_posts WHERE post_id = ANY(%s)",
                    ([post_id for post_id, _, _ in created] + rate_limited_posts,),
                )

    if percentile([1, 2, 3, 4], 0.99) != 4:
        raise AssertionError("nearest-rank tail percentile self-check failed")
    report = {
        "postgresql": True,
        "postgresql_server_version": server_version,
        "rows_submitted": ROWS,
        "concurrent_rows_submitted": CONCURRENT_ROWS,
        "concurrent_moderation_workers": 8,
        "rate_limit_denials": len(rate_limited_ms),
        "rate_limit_denial_ms": round(rate_limited_ms[0], 3),
        "concurrent_moderation_total_ms": round(concurrent_total_ms, 3),
        "approved_rows_checked_per_feed": ROWS // 2 + CONCURRENT_ROWS,
        "rejected_rows_checked_per_feed": ROWS // 2,
        "feed_reads": len(read_ms),
        "percentile_method": "nearest-rank ceil(p*n)-1",
        "latency_ms": {
            name: {f"p{int(p * 100)}": percentile(values, p) for p in (0.5, 0.95, 0.99)}
            | {"mean": round(statistics.fmean(values), 3)}
            for name, values in (("submit", create_ms), ("moderate", moderation_ms), ("approved_feed", read_ms))
        },
        "concurrent_moderation_latency_ms": {f"p{int(p * 100)}": percentile(concurrent_ms, p) for p in (0.5, 0.95, 0.99)},
        "firebase_calls": 0,
        "external_network_calls": 0,
        "fixture_data_deleted": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
