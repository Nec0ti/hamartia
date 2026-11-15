"""Small shared helpers for reproducible, AI-free benchmark reports."""

import json
import copy
import os
import platform
import struct
import statistics
import time
import zlib
from pathlib import Path


def measure(operation, repeats=5, warmups=1):
    for _ in range(warmups):
        operation()
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - started)
    ordered = sorted(samples)
    return {
        "samples": repeats,
        "p50_seconds": round(statistics.median(samples), 6),
        "p95_seconds": round(ordered[max(0, (repeats * 95 + 99) // 100 - 1)], 6),
    }


def metadata(seed=None):
    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "processor": platform.processor() or "not reported",
        "logical_cpus": os.cpu_count(), "seed": seed,
    }


def seeded_png(width, height, rng):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    pixels = b"".join(b"\0" + rng.randbytes(width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels, 1)) + chunk(b"IEND", b""))


def emit(result, json_output=None):
    result["environment"] = metadata(result.get("seed"))
    result["ai_included"] = False
    encoded = json.dumps(result, sort_keys=True)
    if json_output:
        Path(json_output).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


def assert_oracle(actual, expected, label="benchmark oracle"):
    """Compare complete outputs against precomputed expected values."""
    if actual != expected:
        raise AssertionError(f"{label} mismatch")


def probe_oracle_self_check(actual, expected, mutate, label):
    """Check that the oracle comparator rejects a handcrafted output perturbation.

    This is correctness harness self-checking only. It is never called in a timed
    operation and intentionally does not contribute a benchmark sample. It checks
    comparator wiring/sensitivity, not code-level mutation testing.
    """
    perturbed = copy.deepcopy(actual)
    mutate(perturbed)
    try:
        assert_oracle(perturbed, expected, label)
    except AssertionError:
        return label
    raise AssertionError(f"oracle failed to reject perturbation: {label}")
