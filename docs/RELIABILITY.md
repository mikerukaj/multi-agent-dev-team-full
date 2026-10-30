# Reliability

How a run survives the failures of the services it depends on, checks everything the model says before using it, and can be stopped and resumed. The code is in `resilience/`, `orchestration/validation.py` and `orchestration/checkpoint.py`.

## Retries, circuit breakers and graceful degradation

Each outside dependency (the model service per model, the MCP file-tool server, the
sandbox and Chroma) has a **guard** for the run (`resilience/`):

1. **Classify.** Rate limits, overload, 5xx, 408/409 and lost connections are
   *temporary*; refusals, bad requests and bad credentials are *permanent* and never
   retried. A Docker start failure (exit 125 with a daemon message) is temporary; the
   generated code's own exit codes and timeouts are results, never failures.
2. **Retry** temporary failures up to `RETRY_MAX_RETRIES` times with exponential backoff
   and jitter, honouring a `retry-after` that fits under the cap. A file-tool server that
   dies is restarted for the same workspace and protections inside a retry.
3. **Circuit breaker.** After `CIRCUIT_FAILURE_THRESHOLD` (3) consecutive failed calls
   the circuit opens and calls fail fast; after `CIRCUIT_COOLDOWN_SECONDS` (30) one trial
   call is let through (half-open). The Coder and QA share a breaker when they share a
   model.
4. **Degrade, never crash.** A model call that can't be served is answered from the
   response cache (`.cache/llm/`, only a reply that still validates) or ends the run
   `dependency_unavailable` (resumable, exit 3). A tool call returns a structured error
   to the agent; a memory failure skips the memory. A *permanent* failure keeps the
   agent's own end reason (for example `pm_error`) and exits 1.

| Setting | Default | Range |
|---|---|---|
| `RETRY_MAX_RETRIES` | `3` | 0–5 |
| `RETRY_BASE_DELAY_SECONDS` / `RETRY_MAX_DELAY_SECONDS` | `1` / `60` | 0.1–10 / 1–300 |
| `CIRCUIT_FAILURE_THRESHOLD` | `3` | 1–10 |
| `CIRCUIT_COOLDOWN_SECONDS` | `30` | 1–3600 |
| `LLM_RESPONSE_CACHE_TTL_SECONDS` / `LLM_RESPONSE_CACHE_DIR` | `86400` / `.cache/llm` | 0 turns the cache off |

## Validating model output

Every structured reply (the PM's spec and consolidation, the Coder's summary and
critique, QA's tests, disputes and review) is checked against a `TypedDict` in
`orchestration/state.py` before any field is read, by a small standard-library validator
(`orchestration/validation.py`). So is the input of every tool call the Coder's model
asks for, and every cached reply served in a degraded call. A reply that fails takes the
agent's existing malformed-output path (QA asks once more with the reason), nothing in it
is acted on, and a `validation_failed` event names the problems. A unit test keeps each
JSON schema sent to the model and its `TypedDict` in step.

## Resuming a run

Each completed stage (the plan, each build task, each reflection, each QA review, each
fix round) saves `workspace/.runs/<run_id>/checkpoint.json`: the state, the settings,
the usage so far and a snapshot of the workspace, written atomically. A run that ended
`interrupted`, `dependency_unavailable`, `a2a_failed` or `budget_exceeded` (or was
killed outright) can be continued:

```bash
python -m orchestration.team --resume 20261020-142233-a1b2c3 [--budget 2.00]
```

The workspace is restored to the checkpoint (the files changed or removed are recorded),
and the run continues from the next stage with the same run ID, iteration count, usage,
cost and A2A log. Only the budget may change, and only upwards; any other setting change
is refused. A run that is still going (its lock is held), that ended for good, or whose
checkpoint is missing or incompatible is refused with exit 2 and no file changed. The
Coder's long-term memory is not rolled back. A stop signal (Ctrl-C or SIGTERM) ends a
run cleanly within seconds: its containers are killed, its record is written, QA's report
is marked partial, and it exits 130 or 143; a second signal exits at once.

## Exit codes

The final run state is printed to stdout as JSON (redacted), then the cost report's path,
QA's report path and, with tracing on, the trace URL go to stderr. Exit codes:

- **0:** the run completed.
- **1:** the run ended for good: `failed`, `rejected` or `error` with an end reason that
  can't be resumed.
- **2:** a usage error: an empty requirement, a bad setting (including an iteration limit
  outside 1–10), a failing health item (no Docker, no credentials, …), or a refused
  resume.
- **3:** the run ended with a resumable end reason: `dependency_unavailable`,
  `a2a_failed` or `budget_exceeded`.
- **130 / 143:** the run was interrupted by SIGINT / SIGTERM (also resumable).

```python
from orchestration.team import run_team

state = run_team("A tool that prints the primes below 50", max_iterations=3)
print(state["status"], state["end_reason"], len(state["iterations"]))
```
