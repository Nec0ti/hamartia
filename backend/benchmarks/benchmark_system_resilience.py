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
from contextlib import contextmanager
from pathlib import Path

from app.services.storage import StorageService
from benchmark_common import emit, probe_oracle_self_check


def percentile(samples, percent):
    return sorted(samples)[max(0, (len(samples) * percent + 99) // 100 - 1)]


def timing(samples):
    return {
        "samples": len(samples), "p50_seconds": round(statistics.median(samples), 6),
        "p95_seconds": round(percentile(samples, 95), 6),
    }


@contextmanager
def loopback_only():
    original = socket.socket.connect

    def guarded(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if not loopback:
            raise AssertionError(f"benchmark blocked non-loopback connection: {host}")
        return original(sock, address)

    import ipaddress
    socket.socket.connect = guarded
    try:
        yield
    finally:
        socket.socket.connect = original


def request_json(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read())


def seeded_payload(seed, index):
    rng = random.Random((seed << 16) + index)
    # Independent request vectors include zero-only, all-blank, and tied date/subject cases.
    cases = [
        ("2026-01-01", "Physics", 0, 0, 0),
        ("2026-01-01", "Physics", 0, 0, 7),
        ("2026-01-02", "Math", 8, 2, 1),
        ("2026-01-03", "Biology", 3, 9, 0),
    ]
    date, subject, correct, incorrect, blank = cases[index % len(cases)]
    if index % len(cases) >= 2:
        correct += rng.randrange(0, 2)
    return {
        "date": date, "exam_type": "branch", "subject": subject,
        "correct": correct, "incorrect": incorrect,
        "blank": blank, "duration_minutes": 20 + index % 10, "duration_seconds": index % 60,
    }


def start_api(data_dir, port, guard_dir):
    (guard_dir / "sitecustomize.py").write_text(
        "import ipaddress, socket\n"
        "_connect = socket.socket.connect\n"
        "def _loopback_only(sock, address):\n"
        " host = address[0] if isinstance(address, tuple) else address\n"
        " try: allowed = ipaddress.ip_address(host).is_loopback\n"
        " except ValueError: allowed = host == 'localhost'\n"
        " if not allowed: raise RuntimeError('non-loopback network blocked: ' + str(host))\n"
        " return _connect(sock, address)\n"
        "socket.socket.connect = _loopback_only\n", encoding="utf-8")
    env = os.environ.copy()
    env["HAMARTIA_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = os.pathsep.join([str(guard_dir), str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
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
            expected_shapes = [dict(row) for row in payloads]
            started_all = time.perf_counter()
            latencies = []
            results = []
            lock = threading.Lock()

            def send(item):
                index, payload = item
                begin = time.perf_counter()
                status, result = request_json(base, "POST", payload)
                elapsed = time.perf_counter() - begin
                assert status == 201
                for key, value in payload.items():
                    assert result[key] == value, f"serialized response mismatch for {key}"
                assert result["id"].startswith("exam_") and isinstance(result["net"], (float, int))
                with lock:
                    latencies.append(elapsed)
                    results.append(result)

            with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
                list(pool.map(send, enumerate(payloads)))
            wall = time.perf_counter() - started_all
            status, persisted = request_json(base)
            assert status == 200 and len(results) == len(payloads) and len(persisted) == len(payloads)
            ids = [r["id"] for r in results]
            assert len(set(ids)) == len(ids), "API response identifiers must be unique"
            by_id = {r["id"]: r for r in results}
            persisted_by_id = {row["id"]: row for row in persisted}
            assert persisted_by_id == by_id, "full persisted API output differs from serialized responses"
            canonical_responses = sorted(results, key=lambda r: r["id"])
            canonical_persisted = sorted(persisted, key=lambda r: r["id"])
            response_probe = probe_oracle_self_check(
                canonical_persisted, canonical_responses, lambda rows: rows.pop(),
                "missing-loopback-response-record perturbation",
            )
            for seed_index, seed in enumerate(seeds):
                offset = seed_index * clients * requests_per_client
                shapes = expected_shapes[offset:offset + clients * requests_per_client]
                assert all(any(all(row.get(k) == v for k, v in shape.items()) for row in persisted) for shape in shapes), "persisted request vector missing"
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
                "seeds": seeds, "serialized_requests": len(payloads), "serialized_response_bytes": sum(len(json.dumps(r, separators=(",", ":")).encode()) for r in results),
                "http_request_latency": timing(latencies), "concurrent_wall_seconds": round(wall, 6),
                "http_requests_per_second": round(len(payloads) / wall, 3),
                "direct_storage_append_latency": timing(direct_samples),
                "oracle": "request fields round-trip; complete persisted ID-to-response equality; unique generated IDs; all hand-authored edge vector shapes present",
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
    with tempfile.TemporaryDirectory(prefix="hamartia-system-resilience-") as temporary:
        root = Path(temporary)
        contention = multiprocess_writers(root, args.workers, args.writes)
        recovery = crash_and_recover(root)
        http = http_benchmark(root, args.clients, args.requests_per_client, args.seeds)
    emit({
        "benchmark": "system_resilience_and_loopback_http", "multiprocess_storage": contention,
        "atomic_replace_crash_recovery": recovery, "loopback_http": http,
        "fault_and_correctness_checks_timed": False,
        "network_boundary": "API child connect guard rejects non-loopback socket targets; benchmark client guard rejects non-loopback targets; only /exams is called; no settings or AI route is contacted",
        "ai_included": False,
    }, args.json_output)


if __name__ == "__main__":
    main()
