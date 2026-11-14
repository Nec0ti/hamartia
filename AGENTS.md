# Hamartia project rules

- First read `backlog.md`, `notes.md`, and the latest reports; keep scope small and verifiable.
- Make a separate commit for each completed code change. Do not commit experimental or broken intermediate states.
- Before changing a data format, inspect `backend/data` compatibility and the rollback path; do not delete user data.
- Local AI will be tried on a separate machine. Model execution, quality, latency, and resource usage are outside the test/benchmark scope.
- Include all main flows other than AI in suitable tests and benchmarks; state the measurement method in the report.
- Before considering a feature complete, run the relevant checks and save the result under `reports/`.
- Update API and UI contracts together; search for existing client calls before changing shared code.
- Do not copy the names or content of external learning platforms; keep Hamartia's data and user flows original.
