# End-to-end results

Three short, realistic development tasks run through the whole live pipeline
(PM → Coder ⇄ QA), one of each shape. They are kept out of the fixed benchmark so its
results stay comparable. The tasks are in
[`benchmarks/e2e_tasks.json`](../benchmarks/e2e_tasks.json):

| Task | Kind | Requirement (short) |
|---|---|---|
| `slugify-cli` | Command-line tool | Join the arguments into a URL slug; with no arguments, print usage and exit 2 |
| `isbn-check` | Library with input validation | `is_valid_isbn10` / `is_valid_isbn13` with hyphens and checksums; never raise |
| `lru-cache` | Stateful component | `LRUCache(capacity)` with `get`/`put`, least-recently-used eviction; capacity below 1 raises |

```bash
RUN_BUDGET_USD=2 python -m benchmarks.run_benchmark --requirements benchmarks/e2e_tasks.json --label e2e-before
```

Each task is meant to cost under $0.50 per run. A task that costs more is replaced with a
smaller one of the same kind.

## Results

**Not yet run.** The first attempt on 2026-10-30 stopped at the PM's first model call
with `401 invalid x-api-key`, before any spend: the configured API key had been revoked.
This table is filled in from the committed results files once the runs are made.

| Task | Kind | Result | End reason | QA reviews | Tokens | Cost | Duration |
|---|---|---|---|---:|---:|---:|---:|
| `slugify-cli` | cli | not run | – | – | – | – | – |
| `isbn-check` | library | not run | – | – | – | – | – |
| `lru-cache` | stateful | not run | – | – | – | – | – |

## Failures and fixes

Every failure, its cause and its fix, with the commit and the result of the re-run, is
recorded here as the runs are made.

| When | Symptom | Cause | Fix | Re-run |
|---|---|---|---|---|
| 2026-10-30 | All three runs: `pm_error`, `401 invalid x-api-key` on the first call | The API key in `.env` had been revoked | None in the system (environmental). The health check only checks that a key is set, so an invalid key shows up on the first call, before any spend | Waiting for a valid key |

## Final status

Not yet run (see above).
