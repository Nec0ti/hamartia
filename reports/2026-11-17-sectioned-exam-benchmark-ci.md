# Sectioned exam benchmark in backend CI

Date: 2026-11-17

## Scope

Added the existing persisted, host-only sectioned TYT/AYT Study Agent benchmark to the backend job in `.github/workflows/ci.yml`, using the same three-repeat command pattern as the adjacent Study Agent benchmarks. This is internal verification coverage; it does not change app behavior or add a dependency. The benchmark keeps its fail-fast patches on every `AIService` provider entry point and reports `ai_included: false`.

## Resource assessment

- The same benchmark command completed locally in 14.17 seconds on Python 3.14.8 with eight logical CPUs. It consumed 12.85 seconds of user CPU and 0.56 seconds of system CPU.
- The latest successful backend job available during this change, [run 43965736616](https://github.com/Nec0ti/hamartia/actions/runs/43965736616), took 119 seconds. The local benchmark duration is about 12% of that run; it remains well within the backend job's existing 15-minute timeout.
- Local timing is indicative only: CI uses Python 3.12 and runner performance varies. The existing timeout is unchanged.

## Verification

Command:

```sh
PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_study_agent_sectioned_exam.py --repeats 3
```

It passed locally. The 24-record workload reported 0.688791-second p50 and 0.715204-second p95 preview-plus-create time; the 64-record workload reported 2.306835-second p50 and 2.331589-second p95. Both workloads reported zero provider tripwire calls, and the full persisted-row, section-order, scoring, retry, race, and wrong-result oracles passed. The added GitHub Actions step has not yet run; PR CI is the remaining verification.

No provider, local model, or external service was invoked.
