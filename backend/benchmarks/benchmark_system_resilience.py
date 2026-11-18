"""Bounded multi-process storage/recovery and loopback HTTP benchmark; no AI routes."""

import argparse
import concurrent.futures
import json
import os
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from unittest.mock import DEFAULT, patch
from uuid import UUID

from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, probe_oracle_self_check
from benchmark_network_guard import loopback_only


def percentile(samples, percent):
    return sorted(samples)[max(0, (len(samples) * percent + 99) // 100 - 1)]


def timing(samples):
    return {
        "samples": len(samples), "p50_seconds": round(statistics.median(samples), 6),
        "p95_seconds": round(percentile(samples, 95), 6),
    }


def self_check_loopback_guard():
    harmless_returns = {
        "connect": None, "connect_ex": 0, "send": 1, "sendall": None,
        "sendto": 1, "sendmsg": 1,
    }
    with patch.object(socket.socket, "getpeername", return_value=("127.0.0.1", 9)):
        with patch.multiple(socket.socket, **{
            name: DEFAULT
            for name in harmless_returns if hasattr(socket.socket, name)
        }) as original_methods:
            with patch.multiple(socket, **{
                name: DEFAULT
                for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "getnameinfo") if hasattr(socket, name)
            }) as original_resolvers:
                for name, value in harmless_returns.items():
                    if name in original_methods:
                        original_methods[name].return_value = value
                if "getaddrinfo" in original_resolvers:
                    original_resolvers["getaddrinfo"].return_value = []
                if "gethostbyname" in original_resolvers:
                    original_resolvers["gethostbyname"].return_value = "127.0.0.1"
                if "gethostbyname_ex" in original_resolvers:
                    original_resolvers["gethostbyname_ex"].return_value = ("127.0.0.1", [], ["127.0.0.1"])
                if "getnameinfo" in original_resolvers:
                    original_resolvers["getnameinfo"].return_value = ("127.0.0.1", "9")
                with loopback_only():
                    with socket.socket() as probe:
                        for name, operation in (
                            ("connect", lambda: probe.connect(("203.0.113.1", 9))),
                            ("connect_ex", lambda: probe.connect_ex(("203.0.113.1", 9))),
                            ("sendto", lambda: probe.sendto(b"x", ("203.0.113.1", 9))),
                            ("sendmsg", lambda: probe.sendmsg([b"x"], [], 0, ("203.0.113.1", 9))),
                        ):
                            if not hasattr(socket.socket, name):
                                continue
                            try:
                                operation()
                            except RuntimeError as exc:
                                if "blocked" not in str(exc):
                                    raise
                            else:
                                raise AssertionError(f"{name} guard allowed a synthetic non-loopback address")
                        for operation in (
                            lambda: socket.getaddrinfo("provider.invalid", 443),
                            lambda: socket.gethostbyname("provider.invalid"),
                            lambda: socket.gethostbyname_ex("provider.invalid"),
                            lambda: socket.gethostbyaddr("203.0.113.1"),
                            lambda: socket.getnameinfo(("203.0.113.1", 9), 0),
                            lambda: socket.getfqdn("provider.invalid"),
                        ):
                            try:
                                operation()
                            except RuntimeError as exc:
                                if "blocked" not in str(exc):
                                    raise
                            else:
                                raise AssertionError("DNS/name-resolution guard allowed a synthetic hostname")
                        probe.connect(("127.0.0.1", 9))
                        probe.connect_ex(("127.0.0.1", 9))
                        probe.send(b"x")
                        probe.sendall(b"x")
                        probe.sendto(b"x", ("127.0.0.1", 9))
                        if hasattr(socket.socket, "sendmsg"):
                            probe.sendmsg([b"x"], [], 0, ("127.0.0.1", 9))
                        socket.getaddrinfo("127.0.0.1", 9)
                        socket.gethostbyname("127.0.0.1")
                        socket.gethostbyname_ex("127.0.0.1")
                        socket.getnameinfo(("127.0.0.1", 9), 0)
                for name, mock in original_methods.items():
                    if name == "getpeername":
                        continue
                    mock.assert_called_once()
                for name, mock in original_resolvers.items():
                    mock.assert_called_once()


def self_check_unix_socketpair_guard():
    if not hasattr(socket, "AF_UNIX") or not hasattr(socket, "socketpair"):
        return "skipped_unavailable"
    try:
        left, right = socket.socketpair()
    except (OSError, NotImplementedError):
        return "skipped_unavailable"
    try:
        left.settimeout(1)
        right.settimeout(1)
        with loopback_only():
            left.send(b"a")
            assert right.recv(1) == b"a"
            left.sendall(b"b")
            assert right.recv(1) == b"b"
            if hasattr(socket.socket, "sendmsg"):
                left.sendmsg([b"c"])
                assert right.recv(1) == b"c"
    finally:
        left.close()
        right.close()
    return "passed"


def request_json(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read())


def seeded_payload(seed, index):
    rng = random.Random((seed << 16) + index)
    # Independent request vectors include zero-only, all-blank, and tied date/subject cases.
    cases = [
        ("2026-01-01", "Physics", 0, 0, 0, 20),
        ("2026-01-01", "Physics", 0, 0, 7, 20),
        ("2026-01-02", "Math", 8, 2, 1, 22),
        ("2026-01-03", "Biology", 3, 9, 0, 23),
    ]
    date, subject, correct, incorrect, blank, duration_minutes = cases[index % len(cases)]
    if index % len(cases) >= 2:
        correct += rng.randrange(0, 2)
    return {
        "date": date, "exam_type": "branch", "subject": subject,
        "correct": correct, "incorrect": incorrect,
        "blank": blank, "duration_minutes": duration_minutes, "duration_seconds": index % 60,
    }


def expected_exam_response(payload, response, started_at, finished_at):
    """Build the full route result without importing Hamartia's formula helpers."""
    record_id = response.get("id", "")
    assert record_id.startswith("exam_") and len(record_id) == 37
    UUID(hex=record_id[5:])
    created_at = response.get("created_at", "")
    parsed_created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert started_at.replace(microsecond=0) <= parsed_created_at <= finished_at.replace(microsecond=0), "created_at must be a real UTC timestamp inside the request window"

    correct, incorrect = payload["correct"], payload["incorrect"]
    total = correct + incorrect
    net = Fraction(4 * correct - incorrect, 4)
    duration = max(payload["duration_minutes"], 1)
    earned = max(0, int(net * correct * Fraction(3, 2) - duration * incorrect * Fraction(1, 4)))
    # Hand-authored control vectors keep the oracle anchored to known outputs.
    if payload["subject"] == "Physics" and payload["correct"] == payload["incorrect"] == payload["blank"] == 0:
        assert (net, earned, total) == (0, 0, 0)
    if payload["subject"] == "Physics" and payload["correct"] == payload["incorrect"] == 0 and payload["blank"] == 7:
        assert (net, earned, total) == (0, 0, 0)
    if payload["subject"] == "Math":
        assert (float(net), earned) == ((7.5, 79) if correct == 8 else (8.5, 103))
    if payload["subject"] == "Biology":
        assert earned == 0

    expected = dict(payload)
    expected.update({
        "id": record_id, "created_at": created_at, "sections": [],
        "total": total, "net": float(net), "xp": earned,
        "scoring_profile": {
            "profile_id": "legacy-yks", "version": 1,
            "display_name": "YKS (legacy)", "country_label": "Türkiye",
            "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
        },
    })
    return expected


def child_guard_source():
    return "from benchmark_network_guard import install_loopback_guard\n" "install_loopback_guard()\n" "HAMARTIA_NETWORK_GUARD_INSTALLED = True\n"

def self_check_child_guard(guard_dir):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(guard_dir), str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
    probe = '''import ipaddress, socket, sitecustomize
assert sitecustomize.HAMARTIA_NETWORK_GUARD_INSTALLED is True
def must_block(name, operation):
    try:
        operation()
    except RuntimeError as exc:
        if "blocked" not in str(exc):
            raise
    else:
        raise AssertionError(name + " escaped child network guard")

for name in ("connect", "connect_ex"):
    sock = socket.socket()
    try:
        must_block(name, lambda: getattr(sock, name)(("203.0.113.1", 9)))
    finally:
        sock.close()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    must_block("sendto", lambda: sock.sendto(b"x", ("203.0.113.1", 9)))
    if hasattr(sock, "sendmsg"):
        must_block("sendmsg", lambda: sock.sendmsg([b"x"], [], 0, ("203.0.113.1", 9)))
finally:
    sock.close()
for name, operation in (
    ("getaddrinfo", lambda: socket.getaddrinfo("203.0.113.1", 9)),
    ("gethostbyname", lambda: socket.gethostbyname("benchmark.invalid")),
    ("gethostbyname_ex", lambda: socket.gethostbyname_ex("benchmark.invalid")),
    ("gethostbyaddr", lambda: socket.gethostbyaddr("203.0.113.1")),
    ("getnameinfo", lambda: socket.getnameinfo(("203.0.113.1", 9), 0)),
    ("getfqdn", lambda: socket.getfqdn("benchmark.invalid")),
):
    must_block(name, operation)
original_getpeername = socket.socket.getpeername
socket.socket.getpeername = lambda _sock: ("203.0.113.1", 9)
sock = socket.socket()
try:
    must_block("send", lambda: sock.send(b"x"))
    must_block("sendall", lambda: sock.sendall(b"x"))
finally:
    sock.close()
    socket.socket.getpeername = original_getpeername
resolved = socket.getaddrinfo("127.0.0.1", 9)
assert resolved and all(ipaddress.ip_address(item[4][0]).is_loopback for item in resolved)
if hasattr(socket, "AF_UNIX") and hasattr(socket, "socketpair"):
    left, right = socket.socketpair()
    try:
        left.settimeout(1)
        right.settimeout(1)
        left.sendall(b"local")
        assert right.recv(5) == b"local"
    finally:
        left.close()
        right.close()
print("child network guard loaded and rejected synthetic outbound paths")
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], env=env, capture_output=True, text=True,
        timeout=5, check=False,
    )
    if result.returncode or "child network guard loaded" not in result.stdout:
        raise AssertionError(f"API child network guard self-check failed: {result.stdout} {result.stderr}")


def start_api(data_dir, port, guard_dir):
    (guard_dir / "sitecustomize.py").write_text(child_guard_source(), encoding="utf-8")
    self_check_child_guard(guard_dir)
    env = os.environ.copy()
    env["HAMARTIA_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = os.pathsep.join([str(guard_dir), str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
    log = open(guard_dir / "uvicorn.log", "wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
        cwd=Path(__file__).resolve().parents[1], env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    return proc, log


def wait_ready(proc, url):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            status, result = request_json(url)
            if status == 200 and result == []:
                return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("loopback API did not become ready; process_status=" + str(proc.poll()))


def worker_process(data_dir, worker, count, ready, gate):
    worker, count = int(worker), int(count)
    ready = Path(ready)
    gate = Path(gate)
    storage = StorageService(Path(data_dir))
    ready.write_text("ready", encoding="ascii")
    while not gate.exists():
        time.sleep(0.002)
    for ordinal in range(count):
        storage.append_list("writers.json", {
            "id": f"writer-{worker:02d}-{ordinal:03d}", "worker": worker,
            "ordinal": ordinal, "value": worker * 1000 + ordinal,
        }, dict)


def run_writer(data_dir, worker, count, ready, gate):
    code = (
        "from benchmark_system_resilience import worker_process; import sys; "
        "worker_process(*sys.argv[1:])"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
    return subprocess.Popen([sys.executable, "-c", code, str(data_dir), str(worker), str(count), str(ready), str(gate)], env=env)


def multiprocess_writers(root, workers, writes):
    data_dir = root / "writers"
    data_dir.mkdir()
    ready_dir = root / "ready"
    ready_dir.mkdir()
    gate = root / "start"
    processes = [run_writer(data_dir, w, writes, ready_dir / str(w), gate) for w in range(workers)]
    deadline = time.monotonic() + 10
    while len(list(ready_dir.iterdir())) != workers and time.monotonic() < deadline:
        time.sleep(0.005)
    assert len(list(ready_dir.iterdir())) == workers, "all writer processes must reach the contention gate"
    started = time.perf_counter()
    gate.touch()
    for proc in processes:
        assert proc.wait(timeout=20) == 0, "writer process failed"
    elapsed = time.perf_counter() - started
    actual = StorageService(data_dir).load_list("writers.json", dict)
    expected = [
        {"id": f"writer-{w:02d}-{n:03d}", "worker": w, "ordinal": n, "value": w * 1000 + n}
        for w in range(workers) for n in range(writes)
    ]
    assert sorted(actual, key=lambda r: r["id"]) == sorted(expected, key=lambda r: r["id"]), "multiprocess writers lost or altered records"
    canonical_actual = sorted(actual, key=lambda r: r["id"])
    canonical_expected = sorted(expected, key=lambda r: r["id"])
    rejected = probe_oracle_self_check(canonical_actual, canonical_expected, lambda rows: rows.pop(), "missing-writer-record perturbation")
    return {"workers": workers, "writes_per_worker": writes, "expected_records": len(expected), "persisted_records": len(actual), "contention_seconds": round(elapsed, 6), "oracle": "complete independently authored record equality", "wrong_result_probe": rejected}


def crash_and_recover(root):
    data_dir = root / "crash"
    storage = StorageService(data_dir)
    before = [
        {"id": "hand-a", "value": 17}, {"id": "hand-b", "value": 0},
        {"id": "hand-c", "value": -3},
    ]
    storage.save_list("records.json", before)
    code = (
        "import os, sys; from pathlib import Path; from app.services.storage import StorageService; "
        "p=Path(sys.argv[1]); original=Path.replace; "
        "Path.replace=lambda self,target: os._exit(73) if self.name=='records.tmp' else original(self,target); "
        "StorageService(p).append_list('records.json', {'id':'never-committed','value':99}, dict)"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    killed = subprocess.run([sys.executable, "-c", code, str(data_dir)], env=env, check=False, timeout=10)
    assert killed.returncode == 73, f"writer should terminate immediately before replace, got {killed.returncode}"
    restart = StorageService(data_dir)
    recovered = restart.load_list("records.json", dict)
    assert recovered == before, "restart must read the last complete committed state"
    assert (data_dir / "records.tmp").exists(), "simulated termination should leave the uncommitted temp file"
    restart.append_list("records.json", {"id": "after-restart", "value": 41}, dict)
    final = restart.load_list("records.json", dict)
    assert final == [*before, {"id": "after-restart", "value": 41}], "post-restart mutation must reconcile to complete expected state"
    assert not (data_dir / "records.tmp").exists(), "successful replacement must remove abandoned temp file"
    return {"kill_exit": killed.returncode, "last_committed_records": len(before), "post_restart_records": len(final), "reconciliation": "prior complete state survived; abandoned temp ignored and replaced; new record committed"}


def http_benchmark(root, clients, requests_per_client, seeds):
    data_dir = root / "api"
    data_dir.mkdir()
    guard_dir = root / "guard"
    guard_dir.mkdir()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}/exams"
    assert base.startswith("http://127.0.0.1:") and base.endswith("/exams"), "API target must be loopback exams route"
    proc, log = start_api(data_dir, port, guard_dir)
    try:
        with loopback_only():
            try:
                wait_ready(proc, base)
            except RuntimeError as exc:
                log.flush()
                raise RuntimeError(f"{exc}; server_log={(guard_dir / 'uvicorn.log').read_text(errors='replace')}") from exc
            payloads = [seeded_payload(seed, i) for seed in seeds for i in range(clients * requests_per_client)]
            payloads[-1]["subject"] = "Payload " + ("x" * 4096)
            started_all = time.perf_counter()
            request_started_at = datetime.now(timezone.utc)
            latencies = []
            results = []
            response_pairs = []
            lock = threading.Lock()

            def send(item):
                index, payload = item
                begin = time.perf_counter()
                status, result = request_json(base, "POST", payload)
                elapsed = time.perf_counter() - begin
                assert status == 201
                with lock:
                    latencies.append(elapsed)
                    results.append(result)
                    response_pairs.append((payload, result))

            with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
                list(pool.map(send, enumerate(payloads)))
            wall = time.perf_counter() - started_all
            request_finished_at = datetime.now(timezone.utc)
            expected_responses = [
                expected_exam_response(payload, result, request_started_at, request_finished_at)
                for payload, result in response_pairs
            ]
            for actual, expected in zip(results, expected_responses):
                assert_oracle(actual, expected, "complete serialized Exam response")
            status, persisted = request_json(base)
            assert status == 200 and len(results) == len(payloads) and len(persisted) == len(payloads)
            ids = [r["id"] for r in results]
            assert len(set(ids)) == len(ids), "API response identifiers must be unique"
            by_id = {r["id"]: r for r in results}
            persisted_by_id = {row["id"]: row for row in persisted}
            assert persisted_by_id == by_id, "full persisted API output differs from serialized responses"
            canonical_persisted = sorted(persisted, key=lambda r: r["id"])
            canonical_expected = sorted(expected_responses, key=lambda r: r["id"])
            assert canonical_persisted == canonical_expected, "persisted records differ from independently expected full responses"
            response_probe = probe_oracle_self_check(
                canonical_persisted, canonical_expected,
                lambda rows: rows[0].__setitem__("net", rows[0]["net"] + 0.5),
                "same-ID computed-net corruption",
            )
            # Separate direct-function baseline: same record counts, no HTTP serialization or socket.
            direct_dir = root / "direct"
            direct_dir.mkdir()
            direct = StorageService(direct_dir)
            from app.models.schemas import Exam
            direct_samples = []
            for i, payload in enumerate(payloads):
                record = Exam(id=f"direct-{i}", created_at="2026-01-01T00:00:00Z", **payload)
                begin = time.perf_counter()
                direct.append_list("exams.json", record, Exam)
                direct_samples.append(time.perf_counter() - begin)
            assert len(direct.load_list("exams.json", Exam)) == len(payloads)
            return {
                "target": "127.0.0.1 loopback only", "route": "POST/GET /exams", "ai_routes_called": 0,
                "clients": clients, "requests_per_client_per_seed": requests_per_client,
                "seeds": seeds, "serialized_requests": len(payloads),
                "serialized_request_bytes": sum(len(json.dumps(r, separators=(",", ":")).encode()) for r in payloads),
                "serialized_response_bytes": sum(len(json.dumps(r, separators=(",", ":")).encode()) for r in results),
                "http_request_latency": timing(latencies), "concurrent_wall_seconds": round(wall, 6),
                "http_requests_per_second": round(len(payloads) / wall, 3),
                "direct_storage_append_latency": timing(direct_samples),
                "oracle": "independent full response field equality including defaults, net, XP and timestamp; exact persisted-state equality; UUID validity; hand-authored numeric controls",
                "wrong_result_probe": response_probe,
            }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--writes", type=int, default=8)
    parser.add_argument("--clients", type=int, default=4)
    parser.add_argument("--requests-per-client", type=int, default=4)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1729, 20261115])
    parser.add_argument("--json-output")
    args = parser.parse_args()
    assert 1 <= args.workers <= 8 and 1 <= args.writes <= 25
    assert 1 <= args.clients <= 8 and 1 <= args.requests_per_client <= 10
    assert 1 <= len(args.seeds) <= 4
    self_check_loopback_guard()
    unix_socketpair_check = self_check_unix_socketpair_guard()
    with tempfile.TemporaryDirectory(prefix="hamartia-system-resilience-") as temporary:
        root = Path(temporary)
        contention = multiprocess_writers(root, args.workers, args.writes)
        recovery = crash_and_recover(root)
        http = http_benchmark(root, args.clients, args.requests_per_client, args.seeds)
    emit({
        "benchmark": "system_resilience_and_loopback_http", "multiprocess_storage": contention,
        "atomic_replace_crash_recovery": recovery, "loopback_http": http,
        "fault_and_correctness_checks_timed": False,
        "network_boundary": "Parent and API child guard non-loopback TCP/UDP destinations and DNS; numeric loopback is allowed, AF_UNIX local IPC is permitted and self-checked where available; parent and spawned child self-checks pass; only /exams is called; no settings or AI route is contacted",
        "unix_socketpair_guard_self_check": unix_socketpair_check,
        "ai_included": False,
    }, args.json_output)


if __name__ == "__main__":
    main()
