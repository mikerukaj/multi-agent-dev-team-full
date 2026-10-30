# Observability and cost

What every run records about itself, what it costs, and how that cost is kept down. The code is in `observability/` and `cost/`.

## Events, run summary and LangSmith tracing

Every run writes `workspace/.runs/<run_id>/events.jsonl`: one JSON event per line,
flushed as it happens, each with a timestamp, run ID, agent, stage, event type, severity
and outcome ([tests/fixtures/run-event.schema.json](../tests/fixtures/run-event.schema.json)). Model
calls, tool calls, sandbox runs, A2A exchanges, retries, restarts, circuit changes,
validation failures, budget stops, checkpoints and resumes all produce events.
`LOG_LEVEL` (default `info`) filters what is written; errors and `run_end` always are.
The progress lines on stderr come from these events. At the end, a **summary** (totals
per agent and per stage: calls, tokens, cost, duration, retries, restarts, errors, over
every attempt) goes into `run.json` and the final state.

**LangSmith tracing** is off unless you set `LANGSMITH_TRACING=true` and
`LANGSMITH_API_KEY` (optionally `LANGSMITH_PROJECT` and `LANGSMITH_ENDPOINT`). Each run
attempt is then one `team-run` root trace with an `agent:pm`, `agent:coder` or `agent:qa`
span for every agent invocation, carrying `agent_name`, `token_count`, `tool_calls` and
`duration_ms`, and `llm:*` and `tool:*` spans beneath. QA's reviews and the fix round run
on the A2A broker's threads; the trace headers travel in the A2A message metadata, so
their spans stay in the same trace. The run prints `trace: <url>`. A tracing failure
never fails a run.

**Redaction.** The value of every environment variable whose name contains `KEY`,
`TOKEN`, `SECRET`, `PASSWORD` or `CREDENTIAL` (8 or more characters), and any text shaped
like an Anthropic key, is replaced by `[REDACTED]` in events, error messages, run
records, checkpoints, QA reports, cost reports and everything sent to LangSmith.

## Tokens, cost reports, budgets and prompt caching

- **Models by role.** The PM keeps `claude-sonnet-5-5`, because a bad plan wastes every
  later call. The Coder and QA, which make most of a run's calls, default to
  `claude-haiku-5-5`. Either can be moved back with `CODER_MODEL` / `QA_MODEL`.
  Haiku 5.5 has no server-side refusal fallback, so `*_USE_FALLBACKS` now defaults to
  "on if the model supports it", and `true` with Haiku is refused at start-up.
- **Prompt caching.** System prompts, tool definitions, the Coder's append-only history,
  the sources the critique re-reads and QA's spec, sources and tests are cache-marked, so
  repeats are billed at the cache-read rate. `PROMPT_CACHE_TTL` is `5m` (default), `1h`
  or `off`.
- **Per-agent cost.** Every call is priced by the model that served it from the dated
  table `cost/prices.json` (`PRICE_TABLE_PATH` to override). A model with no price is
  reported as unknown, never guessed.
- **Budget.** `RUN_BUDGET_USD` or `--budget USD` caps a run (no cap by default). The cap
  is checked before every model call, so a run overspends by at most one call; it then
  ends `budget_exceeded` (exit 3), with QA's report still written. A budget with an
  unpriced model is refused at start-up.
- **Cost report.** Every run, however it ends, writes `docs/cost_reports/<run_id>.json`
  (`COST_REPORT_DIR` to override): per-agent tokens and cost, the total, the price-table
  version, the cache TTL, the budget and each attempt. For example:

```json
{
  "schema_version": 1, "run_id": "20261020-142233-a1b2c3",
  "status": "completed", "end_reason": "complete",
  "price_table_version": "2026-10-20", "prompt_cache_ttl": "5m", "budget_usd": null,
  "agents": {
    "pm": {"model": "claude-sonnet-5-5", "models": ["claude-sonnet-5-5"], "model_calls": 1,
           "cached_replays": 0, "prompt_tokens": 1834, "completion_tokens": 912,
           "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.012788},
    "coder": {"model": "claude-haiku-5-5", "...": "..."},
    "qa": {"model": "claude-haiku-5-5", "...": "..."}
  },
  "total": {"model_calls": 23, "prompt_tokens": 210345, "completion_tokens": 18210,
            "cache_read_tokens": 150222, "cache_write_tokens": 21004, "cost_usd": 0.0491},
  "attempts": [{"started_at": "…", "ended_at": "…", "end_reason": "complete",
                "cost_usd": 0.0491}],
  "events_lost": false
}
```

(The numbers are illustrative.) The benchmark reports cost per item and in total, and
`--baseline FILE` compares a run with a stored baseline. The pre-feature baseline is
`benchmarks/results/20261020T053121Z-baseline.json` ($0.762 per item, 9/10 passed). The
benchmark with the Coder and QA on Haiku has **not been run yet**.

## Per-interaction cost

Every `model_call` event names its *operation*: the reply type the call asked for (for
example `PMSpecReply` or `QATestFilesReply`), or `tool_turn` for a step of the Coder's
tool loop. `python -m cost.audit` groups the calls of one or more runs by agent, stage
and operation, and ranks these interactions by cost:

```bash
python -m cost.audit workspace/.runs/<run_id>                 # one run
python -m cost.audit --results benchmarks/results/<file>.json  # every run in a results file
python -m cost.audit --compare BEFORE.json AFTER.json          # before/after deltas, per call too
```

Each run's summed event cost is checked against its cost report, so lost events show up
as warnings. [PERFORMANCE.md](PERFORMANCE.md) uses it to find and cut the most
expensive interaction.
