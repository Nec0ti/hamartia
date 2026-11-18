# Benchmark network-boundary tripwires

## Change

Strengthened the Study Agent CLI host benchmark with fail-fast `socket.connect`, `socket.connect_ex`, and sync/async `httpx` transport tripwires around every measured and adversarial trial. Startup self-checks exercise each tripwire against synthetic calls. The benchmark now reports network attempts as a dynamically counted zero; provider calls and writes remain structurally excluded and are not described as runtime counters.

Strengthened the system-resilience benchmark's parent client and API subprocess guards to reject non-loopback `connect` and `connect_ex` calls. Its startup self-check uses mocked underlying socket methods to prove that both methods reject a reserved documentation address and still permit loopback, without attempting an external connection. The actual HTTP workload remains limited to the local `/exams` route.

No application behavior, provider path, dependency, or benchmark workload changed. No live AI, model, provider, or external network request was made.

## Verification

On Python 3.14.8, Linux x86_64, 8 logical CPUs:

- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_study_agent_cli.py --repeats 3` — passed. Both 24-record and 100-record trials retained the 175 adversarial probes; runtime network tripwires reported zero calls.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python backend/benchmarks/benchmark_system_resilience.py` — passed. Four processes persisted 32/32 records, crash recovery matched its oracle, and all 32 local HTTP requests passed the complete response and stored-row oracles. No AI route was contacted.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_study_agent_cli.py -q` — 22/22 passed.
- `PYTHONPATH=backend /home/necoti/hamartia/.venv/bin/python -m unittest discover -s backend/tests -p test_storage_process_lock.py -q` — 2/2 passed.
- Python compilation and `git diff --check` — passed.

PR CI still needs to run on the submitted commit. The resilience workload intentionally permits loopback traffic to its own temporary API process; it rejects non-loopback TCP connection calls in both the client and child process. These Python-level tripwires are defense-in-depth for this benchmark, not an OS sandbox against native extensions or arbitrary subprocess code.
