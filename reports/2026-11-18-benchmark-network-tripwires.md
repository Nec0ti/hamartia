# Benchmark network-boundary tripwires

## Change

Strengthened the Study Agent CLI host benchmark with fail-fast tripwires for socket connect/send methods, resolver helpers, and sync/async `httpx` transports around every measured and adversarial trial. Startup self-checks exercise every tripwire against synthetic calls. The benchmark now reports network attempts as a dynamically counted zero; provider calls and writes remain structurally excluded and are not described as runtime counters.

Strengthened the system-resilience benchmark's parent client and API subprocess guards to allow numeric loopback TCP/UDP destinations and local `AF_UNIX` IPC, reject non-loopback IP destinations and hostname/reverse DNS, and force numeric `getnameinfo` results. The parent self-check uses mocked underlying methods to prove that non-loopback calls are rejected while numeric loopback calls remain permitted. Where `AF_UNIX` socketpairs are supported, a synthetic local socketpair self-check confirms `send`, `sendall`, and `sendmsg` remain usable; otherwise that portability check reports `skipped_unavailable`. A bounded subprocess loads the actual generated `sitecustomize.py`, verifies its installation sentinel, and exercises synthetic forbidden connect, UDP, and DNS calls without contacting an external address. The actual HTTP workload remains limited to the local `/exams` route.

No application behavior, provider path, dependency, or benchmark workload changed. No live AI, model, provider, or external network request was made.

## Verification

On Python 3.14.8, Linux x86_64, 8 logical CPUs:

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_study_agent_cli.py --repeats 3` — passed. Both 24-record and 100-record trials retained the 175 adversarial probes; runtime network tripwires reported zero calls.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_system_resilience.py` — passed. Four processes persisted 32/32 records, crash recovery matched its oracle, all 32 local HTTP requests passed the complete response and stored-row oracles, and parent/child network-guard self-checks passed. Numeric loopback resolution and HTTP traffic succeeded; the `AF_UNIX` socketpair guard self-check passed on this host; no external target or AI route was contacted.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_study_agent_cli.py -q` — 22/22 passed.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_storage_process_lock.py -q` — 2/2 passed.
- Python compilation and `git diff --check` — passed.

PR CI needs to run on the updated commit. The resilience workload intentionally permits numeric loopback traffic to its own temporary API process and local `AF_UNIX` IPC, while rejecting hostname resolution and non-loopback TCP/UDP calls in both the client and child process. These Python-level tripwires are defense in depth for this benchmark, not an OS sandbox against native extensions or arbitrary subprocess code.
