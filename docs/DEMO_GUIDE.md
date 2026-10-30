# Presenter's guide

A timed run of show for presenting the project live, in a meeting or a recording. The
core demo takes 10 minutes; an optional deep dive adds up to 10 more. Each step gives
the command, what the audience should see, and what to say.

## Pre-flight checklist

Do this 15 minutes before the audience arrives:

- [ ] `source .venv/bin/activate` in a terminal at least 120 columns wide, with a large
  font.
- [ ] `python -m orchestration.health` shows `ok` on every line except the `info` ones.
- [ ] `.env` holds a valid `ANTHROPIC_API_KEY`, and `RUN_BUDGET_USD=2` is set, or plan
  to pass `--budget 2`.
- [ ] The sandbox image is built
  (`docker image inspect multi-agent-sandbox:py3.12-pytest9.1.1`).
- [ ] Chroma's embedding model is cached. Run `python -m demo` once, and one short live
  run if possible; the first run downloads about 80 MB.
- [ ] Browser tabs open: the README, [docs/ARCHITECTURE.md](ARCHITECTURE.md), the
  published sample run's progress log (in the sample-run folder next to this guide, once
  the benchmark refresh has produced it) and [docs/PERFORMANCE.md](PERFORMANCE.md).
- [ ] A second terminal ready in the repository, for the deep dive.

## Core demo (10 minutes)

| Time | Show | Expected | Say |
|------|------|----------|-----|
| 0:00 | The README's first screen and the animated recording | Pitch, highlights, the replay of a run | "A requirement in plain English goes in; tested Python comes out. Three agents, no human in the loop after the first prompt." |
| 1:00 | `python -m demo` | Planning, two build tasks, self-review, `[qa] #1: 6 passed, 1 failed`, a fix round, `[qa] #2: 7 passed`, all in about 11 seconds | "This is the real team with a simulated model and sandbox. QA's test caught a real bug: `-40F` lost its sign. The Coder fixed it, and the second review passed." |
| 2:00 | Start the live run: `python -m orchestration.team "A command-line tool that converts temperatures between Celsius and Fahrenheit" --budget 2` | `[pm]` within about 20 seconds, then `[handoff]` and `[step N]` lines | "Now the real thing, capped at two dollars." |
| 2:30 | While it runs: the data-flow diagram in ARCHITECTURE.md | The diagram | "The graph decides what runs next and guarantees the run ends. The Coder and QA only talk through A2A messages, and every file access goes through an MCP server that enforces the rules, so the Coder can't edit QA's tests." |
| 4:30 | Back to the terminal: the `[reflect]` and `[qa] #1` lines | Critique items; QA's test counts and blocking findings | "Before QA sees anything, the Coder critiques its own code. QA wrote its tests from the specification, ran them for real in a sandbox with no network, and the verdict is decided in code, not by the model." |
| 6:30 | The `[fix]` and `[qa] #2` lines, then `[finish]` | Findings answered, then `complete` | "Each finding is fixed or disputed with a reason; QA decides the disputes against the spec." |
| 8:00 | `workspace/<run_id>/.qa/report.md` and `docs/cost_reports/<run_id>.json` | QA's report; tokens and cost per agent | "Every run leaves a report, a cost breakdown and a checkpoint it can resume from." |
| 9:00 | The README's Results section and [PERFORMANCE.md](PERFORMANCE.md) | Benchmark pass rate; the optimization's before/after delta | "Every number links to the committed evidence behind it." |

If the live run finishes before 8:00, go straight to its report. If it's still running at
8:00, show the published sample run's report instead and come back to the live run
at the end.

## Deep dive (optional, 10 minutes)

| Time | Show | Say |
|------|------|-----|
| 0:00 | `python -m cost.audit workspace/.runs/<run_id>` | "Every model call is tagged with its agent, stage and operation, so I can rank what each interaction cost. That's how the optimization in PERFORMANCE.md was chosen." |
| 2:00 | Start a run, press Ctrl-C after `[qa] #1`, then `python -m orchestration.team --resume <run_id> --budget 2` | "A stop signal ends the run cleanly within seconds; resume continues from the last completed stage with the same run ID." |
| 5:00 | `tests/test_never_crashes.py` and `tests/test_injected_failures.py` | "Every node with every dependency failing ends cleanly, and with one call in five failing the run still reaches the same end." |
| 7:00 | [docs/api/index.html](api/index.html) and `scripts/check.sh` | "Every public function is documented and type-annotated, and CI runs the style checks, 550-plus offline tests with a coverage gate, and an API-docs check on every push." |

## If the live service fails

The model service may be slow, rate-limited or down during the demo. Don't wait on it:

1. **Within the first minute (no `[pm]` line yet):** stop with Ctrl-C and switch to the
   published sample run. Open its `progress.log` and walk
   through it at the same pace as the core demo table. Say: "This is a recorded real run
   from the benchmark; here's the same story."
2. **Partway through (rate limit or outage):** the run retries with backoff, then ends
   with a resumable status (exit code 3). Show that: "It didn't crash. It saved a
   checkpoint at the last completed stage." Continue from the sample run, and if the
   service recovers, finish with `--resume <run_id>`.
3. **Budget reached:** the run ends `budget_exceeded`, still writing QA's report and the
   cost report. Show both, then resume with a higher `--budget` if there's time.

The offline demo (`python -m demo`) never depends on the service, so the first two
minutes of the core demo always work.
