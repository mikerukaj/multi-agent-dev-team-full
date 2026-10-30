# Benchmark

## Method

[`benchmarks/requirements.json`](../benchmarks/requirements.json) is a fixed set of 10
small requirements: command-line tools and libraries with explicit edge cases and no
outside services. Each item is one full, live team run with fresh agents and a fresh
Coder memory store, so nothing carries over between items. A results file records every
item, a fingerprint of the requirements file (so later results can tell whether they are
comparable), and, from 2026-10-29 on, the configuration that produced it.

```bash
python -m benchmarks.run_benchmark --only temp-convert   # one live item, a quick check
python -m benchmarks.run_benchmark --label refresh        # the full evaluation: 10 live runs
```

Two criteria are scored, and the exit code is 0 only for a full run that meets both:

- **Pass rate:** at least 8 of 10 items end with every test passing.
- **Fix rate:** at least 70% of the items whose first draft fails a test end up passing.

## Results by configuration

| Results file | Configuration | Passed | Fix rate | Cost per item |
|---|---|---:|---:|---:|
| [20261020T043138Z-before-qa-fix](../benchmarks/results/20261020T043138Z-before-qa-fix.json) | All three agents on Claude Sonnet 5.5, before the QA fix | 4/10 | 3/3 | ≈ $0.59 (est.) |
| [20261020T053121Z-baseline](../benchmarks/results/20261020T053121Z-baseline.json) | All three agents on Claude Sonnet 5.5, after the QA fix | **9/10** | 3/3 | ≈ $0.76 (est.) |
| Current defaults (PM on Sonnet 5.5; Coder and QA on Haiku 5.5; prompt caching) | **Not yet measured.** The refresh run is waiting on a valid API key | – | – | – |

The two 2026-10-20 runs predate per-call cost tracking, so their cost is **estimated** the
same way for both: input tokens at $2.00 and output tokens at $10.00 per million (Sonnet
5.5, no prompt caching). Prompt caching and the move to Haiku came after them, so these
results describe an earlier, more expensive configuration.

### All-Sonnet, after the QA fix (2026-10-20)

Effort: PM `high`, Coder `medium`, QA `high`. Iteration limit 5.

| Item | Result | End reason | QA reviews | Input tokens | Output tokens | Cost (USD, est.) | Duration (s) |
|---|---|---|---:|---:|---:|---:|---:|
| temp-convert | **passed** | complete | 1 | 118,308 | 18,487 | 0.4215 | 161 |
| word-count | **passed** | complete | 3 | 357,416 | 41,820 | 1.1330 | 341 |
| roman-numerals | **passed** | complete | 1 | 96,089 | 16,231 | 0.3545 | 138 |
| stats | error | qa_failed | 0 | 59,773 | 8,196 | 0.2015 | 155 |
| bank-account | **passed** | complete | 2 | 175,169 | 23,816 | 0.5885 | 229 |
| todo-cli | **passed** | complete | 2 | 357,608 | 40,093 | 1.1161 | 338 |
| csv-summary | **passed** | complete | 2 | 315,121 | 40,362 | 1.0339 | 333 |
| password-strength | **passed** | complete | 2 | 164,129 | 25,053 | 0.5788 | 212 |
| matrix | **passed** | complete | 2 | 234,956 | 26,487 | 0.7348 | 218 |
| rate-limiter | **passed** | complete | 4 | 499,442 | 45,574 | 1.4546 | 398 |

Passed: **9/10** · failing first drafts fixed: 3/3 = 1.00 · total cost ≈ $7.62 ($0.762 per item) · median duration 223 s

The one failure, `stats`, ended `qa_failed` before any test ran. Even on its corrective
attempt, QA listed an acceptance criterion in its own words ("median(numbers) takes a list
of ints/floats and returns the middle value…") instead of copying it from the
specification, and that check rejects the reply. The check is deliberate: it keeps every
test traceable to a stated requirement.

### All-Sonnet, before the QA fix (2026-10-20)

Kept as the record of the defect described in [REFLECTION.md](REFLECTION.md#a-bug-and-how-it-was-resolved):
six items ended `qa_failed` because QA gave up after its first rejected reply.

| Item | Result | End reason | QA reviews | Input tokens | Output tokens | Cost (USD, est.) | Duration (s) |
|---|---|---|---:|---:|---:|---:|---:|
| temp-convert | error | qa_failed | 0 | 125,799 | 14,055 | 0.3921 | 172 |
| word-count | **passed** | complete | 2 | 202,451 | 30,161 | 0.7065 | 249 |
| roman-numerals | error | qa_failed | 0 | 87,672 | 10,655 | 0.2819 | 142 |
| stats | error | qa_failed | 1 | 124,254 | 16,971 | 0.4182 | 175 |
| bank-account | error | qa_failed | 0 | 70,059 | 9,639 | 0.2365 | 116 |
| todo-cli | error | qa_failed | 0 | 239,206 | 21,617 | 0.6946 | 281 |
| csv-summary | error | qa_failed | 0 | 108,696 | 14,377 | 0.3612 | 203 |
| password-strength | **passed** | complete | 4 | 432,655 | 38,471 | 1.2500 | 346 |
| matrix | **passed** | complete | 2 | 228,087 | 26,466 | 0.7208 | 230 |
| rate-limiter | **passed** | complete | 3 | 283,983 | 30,690 | 0.8749 | 264 |

Passed: **4/10** · failing first drafts fixed: 3/3 = 1.00 · total cost ≈ $5.94 ($0.594 per item) · median duration 216 s
