"""Seeded PostgreSQL-backed social profile API oracle and concurrency benchmark."""

import json
import ipaddress
import math
import os
import resource
import socket
import statistics
import time
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.social.application import create_social_app
from app.social.database import PostgresProfileRepository, migrate_social_database
from app.social.security import FirebaseTokenVerifier


PROJECT = "hamartia-social-benchmark"
SEED_COUNT = 64
TIMED_ROWS = 16
REPEATS = 24
WORKERS = 12
CONCURRENT_REPEATS = 12
AVATARS = ("sunrise", "moon", "leaf", "star", "book", "mountain", "wave", "lantern")


def seeded_payload(index):
    return {
        "nickname": f"Synthetic {index:03d}",
        "age": 14 + index % 31,
        "school_grade": f"Grade {index % 13 + 1}",
        "school_class": f"Group {index % 7}",
        "curriculum": f"Synthetic curriculum {index % 4}",
        "study_preferences": f"Synthetic preference row {index}",
        "study_goals": f"Synthetic goal row {index}",
        "avatar_preset": AVATARS[index % len(AVATARS)],
    }


def expected_seeded_profile(index):
    return {
        "nickname": f"Synthetic {index:03d}",
        "age": 14 + index % 31,
        "school_grade": f"Grade {index % 13 + 1}",
        "school_class": f"Group {index % 7}",
        "curriculum": f"Synthetic curriculum {index % 4}",
        "study_preferences": f"Synthetic preference row {index}",
        "study_goals": f"Synthetic goal row {index}",
        "avatar_preset": AVATARS[index % len(AVATARS)],
        "nickname_public": False,
        "age_public": False,
        "school_grade_public": False,
        "school_class_public": False,
        "curriculum_public": False,
        "study_preferences_public": False,
        "study_goals_public": False,
        "avatar_preset_public": False,
    }


class BenchmarkVerifier:
    def __init__(self, users):
        self.users = users

    def __call__(self, token):
        uid = self.users.get(token)
        if uid is None:
            raise AssertionError("unexpected benchmark token")
        return {
            "aud": PROJECT,
            "iss": f"https://securetoken.google.com/{PROJECT}",
            "sub": uid,
            "email": "synthetic-private-claim@example.invalid",
        }


def forbidden(*_args, **_kwargs):
    raise AssertionError("Firebase SDK or network access is forbidden in this benchmark")


def loopback_postgres_target(database_url):
    parsed = urlsplit(database_url)
    host = parsed.hostname
    try:
        is_loopback = host.casefold() == "localhost" or ipaddress.ip_address(host).is_loopback
    except (AttributeError, ValueError):
        is_loopback = False
    if not host or not is_loopback:
        raise SystemExit("benchmark PostgreSQL must use an explicit loopback host")
    try:
        return parsed.port or 5432
    except ValueError as exc:
        raise SystemExit("benchmark PostgreSQL port is invalid") from exc


def guarded_connect(original, postgres_port):
    def connect(sock, address):
        if isinstance(address, tuple) and len(address) >= 2:
            try:
                loopback = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                loopback = False
            if loopback and address[1] == postgres_port:
                return original(sock, address)
        raise AssertionError("unexpected non-PostgreSQL socket connection")
    return connect


def percentile(values, percent):
    ordered = sorted(values)
    # Nearest-rank keeps p95/p99 at the actual upper tail, including small samples.
    index = max(0, min(len(ordered) - 1, math.ceil(percent * len(ordered)) - 1))
    return round(ordered[index], 3)


def main():
    database_url = os.environ.get("HAMARTIA_SOCIAL_BENCHMARK_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("HAMARTIA_SOCIAL_BENCHMARK_DATABASE_URL must use PostgreSQL")
    postgres_port = loopback_postgres_target(database_url)

    import psycopg

    migrate_social_database(database_url)
    with psycopg.connect(database_url) as connection:
        server_version = connection.execute("SHOW server_version").fetchone()[0]
    run_id = uuid4().hex
    uids = [f"bench-{run_id}-{index:03d}" for index in range(SEED_COUNT)]
    users = {f"token-{index:03d}": uid for index, uid in enumerate(uids)}
    repository = PostgresProfileRepository(database_url, max_connections=WORKERS)

    try:
        with psycopg.connect(database_url) as connection:
            for index, uid in enumerate(uids):
                row = seeded_payload(index)
                columns = ("uid", *row)
                names = ", ".join(columns)
                placeholders = ", ".join("%s" for _ in columns)
                connection.execute(
                    f"INSERT INTO social_profiles ({names}) VALUES ({placeholders})",
                    (uid, *(row[column] for column in row)),
                )

        app = create_social_app(PROJECT, BenchmarkVerifier(users), repository)
        get_latencies = []
        patch_latencies = []
        concurrent_latencies = []
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        with patch.object(FirebaseTokenVerifier, "__call__", forbidden), \
                patch.object(socket.socket, "connect", guarded_connect(original_connect, postgres_port)), \
                patch.object(socket.socket, "connect_ex", guarded_connect(original_connect_ex, postgres_port)), \
                TestClient(app) as client:
            # Compare every seeded response against literals independent of the DB repository/model.
            for index, uid in enumerate(uids):
                response = client.get(
                    "/social/me/profile", headers={"Authorization": f"Bearer token-{index:03d}"}
                )
                expected = expected_seeded_profile(index)
                if response.status_code != 200 or response.json() != expected:
                    raise AssertionError(f"seed oracle mismatch for {uid}")
                if uid in response.text or "synthetic-private-claim" in response.text:
                    raise AssertionError("UID or email claim leaked in the profile response")

            for index in range(TIMED_ROWS):
                token = f"token-{index:03d}"
                headers = {"Authorization": f"Bearer {token}"}
                for repeat in range(REPEATS):
                    started = time.perf_counter_ns()
                    response = client.get("/social/me/profile", headers=headers)
                    get_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
                    if response.status_code != 200:
                        raise AssertionError("GET failed during timed run")
                    started = time.perf_counter_ns()
                    response = client.patch(
                        "/social/me/profile", headers=headers,
                        json={"study_goals": f"timed synthetic goal {repeat}"},
                    )
                    patch_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
                    if response.status_code != 200 or response.json()["study_goals"] != f"timed synthetic goal {repeat}":
                        raise AssertionError("PATCH oracle failed during timed run")

            def concurrent_user(index):
                token = f"token-{index:03d}"
                headers = {"Authorization": f"Bearer {token}"}
                times = []
                for repeat in range(CONCURRENT_REPEATS):
                    value = f"concurrent synthetic goal {index}-{repeat}"
                    started = time.perf_counter_ns()
                    response = client.patch("/social/me/profile", headers=headers,
                                            json={"study_goals": value})
                    times.append((time.perf_counter_ns() - started) / 1_000_000)
                    if response.status_code != 200 or response.json()["study_goals"] != value:
                        raise AssertionError("concurrent PATCH oracle mismatch")
                    started = time.perf_counter_ns()
                    response = client.get("/social/me/profile", headers=headers)
                    times.append((time.perf_counter_ns() - started) / 1_000_000)
                    if response.status_code != 200 or response.json()["study_goals"] != value:
                        raise AssertionError("concurrent GET oracle mismatch")
                return times

            with ThreadPoolExecutor(max_workers=WORKERS) as executor:
                for values in executor.map(concurrent_user, range(WORKERS)):
                    concurrent_latencies.extend(values)

            for index in range(WORKERS):
                response = client.get(
                    "/social/me/profile", headers={"Authorization": f"Bearer token-{index:03d}"}
                )
                expected_value = f"concurrent synthetic goal {index}-{CONCURRENT_REPEATS - 1}"
                if response.status_code != 200 or response.json()["study_goals"] != expected_value:
                    raise AssertionError("final concurrent state oracle mismatch")

            stats = repository.stats()
            connection_stats = {key: value for key, value in stats.items()
                                if key in {"pool_size", "pool_available", "pool_min", "pool_max",
                                           "connections_num", "connections_errors", "requests_num",
                                           "requests_queued", "requests_waiting"}}
            rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        summary = {
            "postgresql": True,
            "postgresql_server_version": server_version,
            "percentile_method": "nearest-rank ceil(p*n)-1",
            "seeded_rows": SEED_COUNT,
            "oracle_rows_checked": SEED_COUNT,
            "repeats_per_timed_row": REPEATS,
            "timed_get_requests": len(get_latencies),
            "timed_patch_requests": len(patch_latencies),
            "concurrent_workers": WORKERS,
            "concurrent_requests": len(concurrent_latencies),
            "latency_ms": {
                name: {f"p{int(p * 100)}": percentile(values, p) for p in (0.5, 0.95, 0.99)}
                | {"mean": round(statistics.fmean(values), 3)}
                for name, values in (("get", get_latencies), ("patch", patch_latencies),
                                     ("concurrent", concurrent_latencies))
            },
            "process_peak_rss_kib": rss_kib,
            "pool_max_connections": repository.max_connections,
            "connection_stats": connection_stats,
            "firebase_calls": 0,
            "external_network_calls": 0,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        repository.close()
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM social_profiles WHERE uid = ANY(%s)", (uids,))


if __name__ == "__main__":
    main()
