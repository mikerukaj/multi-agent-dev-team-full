# Testing

The test suite runs offline and makes no paid model call. Every agent, the loop, the protocols and the failure paths are tested; live runs are opt-in.

## Running the tests

```bash
scripts/test.sh                                    # the whole suite with the 85% coverage gate
python -m unittest discover -s tests -t . -v       # the same tests without coverage
```

`scripts/test.sh` is one non-interactive command whose exit status alone says whether
the tests passed and coverage reached 85%, so a CI service can run it unchanged. It runs
offline, makes no paid model call, and finishes in about a minute and a half. The suite
can't reach the real model service: it uses a dummy key and a closed local address.
Tests that need Docker skip with that reason. Live runs, which spend money, happen only with `RUN_LIVE_E2E=1`
(plus a key and Docker): the end-to-end test and the Coder smoke test.

The layers:

- **Unit** (`tests/test_*.py`): each agent with fully mocked model replies, sandbox, MCP
  and memory (`setUpModule` makes any real dependency raise).
- **Integration** (`tests/integration/`): PM + Coder through the real team graph and MCP
  server; Coder + QA over the real broker with real pytest runs; the Coder's loop in the
  real sandbox; the Compose definition; five runs sharing one Chroma server.
- **End to end** (`tests/e2e/`): the whole pipeline on an inventory requirement, checked
  against a supplied pytest fixture the agents never see.

To run the suite inside the image, see [DEPLOYMENT.md](DEPLOYMENT.md#running-the-test-suite-in-the-image).

| Module | Covers |
|--------|--------|
| `test_qa_agent` | QA with mocked code input: findings match the findings schema, every failing test is covered, severity rules, verdict, interface-only test writing, load repair, disputes, tampering, final report |
| `test_test_runner` | JUnit parsing, the loaded/not-loaded rules, the locked-down pytest command, and a real pytest run in the sandbox |
| `test_team_loop` | The loop over a real broker: success at iteration 3, exactly 5 reviews then a report at the limit, step caps, failures, the A2A record, the iteration-limit setting |
| `test_coder_reflection` | Critique, then revision; numbering; retries; rounds; finding responses |
| `test_mcp_server` | The MCP contract: exactly two tools, every error row, protected writes, start-up refusals, no secrets |
| `test_a2a`, `test_broker`, `test_endpoints` | A2A 1.0 shapes and errors; routing, ordering, isolation, cancellation and timeouts; the agent cards and skill handlers |
| `test_agent_isolation` | The Coder and QA never import each other (SC-110) |
| `test_benchmark` | The benchmark file, scoring and runner |
| `test_team_handoff`, `test_team_record`, `test_team_state`, `test_pm_agent`, `test_coder_agent_loop`, `test_tools`, `test_agent_memory` | The PM, the handoff, the Coder loop, tools and memory |
| `test_validation`, `test_model_caller` | The `TypedDict` validator and schema agreement; the single model-call path |
| `test_resilience`, `test_response_cache`, `test_tool_resilience` | Classification, backoff, the circuit breaker; the degraded-response cache; MCP restart and sandbox start retries |
| `test_never_crashes`, `test_injected_failures` | Every node with every dependency failing ends cleanly (SC-216); 1 call in 5 failing still reaches the same end (SC-201) |
| `test_checkpoint`, `test_resume`, `test_lifecycle` | Atomic checkpoints and the run lock; interrupting every stage and resuming; signals, exit codes, container cleanup |
| `test_redaction`, `test_events`, `test_tracing`, `test_secret_sweep` | Secret scrubbing; the event record and summary; LangSmith spans and propagation; no secret in any output (SC-208) |
| `test_cost`, `test_prompt_caching`, `test_model_defaults` | Prices, ledger, budget and cost report; cache markers; models by role |
| `test_health`, `test_coverage_of_end_reasons` | The health check; every end reason and recovery path has a test |

## Checks beyond the unit tests

```bash
scripts/check.sh      # what CI runs: ruff, then the suite with the coverage gate, then the API-docs check
```

- **Style:** `ruff check .` (configuration in `ruff.toml`): PEP 8 with a 99-character
  line, import order, a docstring on every public module, class and function, and a
  return type on every public function.
- **Documentation:** `tests/test_docs.py` checks that every link, path and documented
  command in the published docs exists, that the README stays short and self-contained,
  and that no published file holds a secret.
- **Offline demo:** `tests/test_demo.py` runs `python -m demo` with no key, Docker or
  network, and checks its transcript against `docs/assets/demo.txt`.
- **Continuous integration:** `.github/workflows/ci.yml` runs `scripts/check.sh`'s steps
  on every push to `main` and `dev`.

## Requirement IDs

Test docstrings, code comments and the [API reference](api/index.html) cite IDs such
as `SC-208`, `FR-233` or `research R7`. They refer to the project's internal
specifications, which aren't published. Each one names the requirement or design
decision the code or test exists for.
