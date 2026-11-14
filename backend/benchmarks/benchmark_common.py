"""Small shared helpers for reproducible, AI-free benchmark reports."""

import json
import os
import platform
import statistics
import time
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


def emit(result, json_output=None):
    result["environment"] = metadata(result.get("seed"))
    result["ai_included"] = False
    encoded = json.dumps(result, sort_keys=True)
    if json_output:
        Path(json_output).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
