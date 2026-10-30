# Configuration

Every setting is optional except `ANTHROPIC_API_KEY`. Set them as environment variables
or as entries in `.env`, which is read at start-up and never committed. Command-line
options override the matching variables for one run.

## Command-line options (`python -m orchestration.team`)

| Option | Meaning |
|--------|---------|
| `--max-iterations N` | Most QA reviews per run, 1 to 10 (default `TEAM_MAX_ITERATIONS` or 5) |
| `--max-steps N` | Maximum Coder model calls per task or fix round, 1 to 10 (default 10) |
| `--timeout SECONDS` | Seconds before a run of generated code is killed (default 30) |
| `--budget USD` | Per-run spending cap (default `RUN_BUDGET_USD`, or none) |
| `--resume RUN_ID` | Continue a run from its last checkpoint (no requirement, and no other setting) |

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `TEAM_MAX_ITERATIONS` | `5` | Most QA reviews per run (1 to 10); `--max-iterations` overrides it |
| `A2A_REQUEST_TIMEOUT` | `1800` | Seconds to wait for an A2A answer before giving up |
| `PM_MODEL` | `claude-sonnet-5-5` | PM model ID |
| `PM_EFFORT` | `high` | PM effort: `low`, `medium`, `high`, `xhigh`, or `max` |
| `PM_USE_FALLBACKS` | on if the model supports it (on for Sonnet) | Retry PM requests the model declines on a fallback model |
| `CODER_MODEL` | `claude-haiku-5-5` (was `claude-sonnet-5-5`) | Coder model ID |
| `CODER_EFFORT` | `medium` | Coder effort |
| `CODER_MAX_STEPS` | `10` | Maximum Coder model calls per task (1 to 10) |
| `CODER_REFLECTION_ROUNDS` | `1` | Critique-and-revise rounds before each QA handoff (1 to 3) |
| `CODER_EXEC_TIMEOUT` | `30` | Seconds before generated code is killed |
| `CODER_WORKSPACE` | `workspace` | Folder for per-run workspaces |
| `CODER_CHROMA_PATH` | `.chroma` | Folder for the Coder's long-term memory |
| `CODER_USE_FALLBACKS` | on if the model supports it (off for Haiku) | Retry declined Coder requests on a fallback model; `true` with Haiku is refused |
| `CODER_SANDBOX_IMAGE` | `multi-agent-sandbox:py3.12-pytest9.1.1` | Image for Coder runs and QA test runs (the project image is built locally) |
| `QA_MODEL` | `claude-haiku-5-5` (was `claude-sonnet-5-5`) | QA model ID |
| `QA_EFFORT` | `high` | QA effort |
| `QA_TEST_TIMEOUT` | `60` | Seconds before a QA test run is killed |
| `QA_REPAIR_ATTEMPTS` | `2` | Times QA may repair a test suite that does not load (0 to 3) |
| `QA_USE_FALLBACKS` | on if the model supports it (off for Haiku) | Retry declined QA requests on a fallback model |
| `PROMPT_CACHE_TTL` | `5m` | Prompt-cache lifetime: `5m`, `1h` or `off` |
| `RUN_BUDGET_USD` | unset (no cap) | Per-run spending cap; `--budget` overrides it |
| `PRICE_TABLE_PATH` | `cost/prices.json` | Price table |
| `COST_REPORT_DIR` | `docs/cost_reports` | Cost report folder |
| `LOG_LEVEL` | `info` | Lowest event severity written: `debug`, `info`, `warning`, `error` |
| `RETRY_*`, `CIRCUIT_*`, `LLM_RESPONSE_CACHE_*` | see [Reliability](../README.md#reliability-retries-circuit-breakers-and-graceful-degradation) | Retries, circuit breakers, degraded-response cache |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | off | LangSmith tracing |
| `CHROMA_HOST`, `CHROMA_PORT` | unset, `8000` | Use a Chroma server instead of the embedded `CODER_CHROMA_PATH` |
| `QA_OUTPUT_ROOT` | system temp | Where QA's JUnit folder is created (a host path under Compose) |
