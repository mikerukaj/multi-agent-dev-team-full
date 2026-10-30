# Reflection

This project turns a plain-English requirement into tested Python with three Claude
agents: a Product Manager, a Coder and a QA & Debugger. Looking back, a few decisions
shaped everything else. One bug taught me the most, and there are things I would do
differently.

## Three design decisions

**1. The graph owns the loop; the agents never call each other.** Every run is one
LangGraph `StateGraph` over a typed `TeamState`, and every routing decision lives in a
handful of small functions in `orchestration/team.py`. The Coder and QA talk only through
A2A messages on an in-process broker, copied through JSON at the boundary, and a test
checks that neither module imports the other. I chose this because a multi-agent loop has
to *end*, and I wanted that guarantee in one place I could read and test. A fix round
starts only while QA says `fix_needed` and fewer than `max_iterations` reviews have run,
and every failure routes to `finish`. Keeping the agents decoupled also means either one
could move to its own process without its messages changing, and each can be tested with
the other faked.

**2. QA is a pipeline in code, not a second agent loop.** The QA & Debugger writes tests
from the specification, seeing only each module's public interface on the first pass so
its expected values come from the spec rather than from whatever the code happens to do.
It then runs them with real pytest in a sandbox with no network, and reads the results
from JUnit XML, checked against pytest's own exit code. Severity and the verdict are
decided in code: failing tests and bugs always block, and the run completes only when
the suite loaded, every test passed and no blocking finding is open. I made QA this rigid
because the model is good at writing tests and diagnosing failures, but it shouldn't be
the judge of whether they passed. Nothing the model says can turn a failing test green.

**3. One model-call path.** Every call to Claude, from all three agents, goes through
`ModelCaller` in `agents/llm.py`: retries with backoff, a circuit breaker per model, a
degraded answer from a validated cache, prompt-cache markers, validation of the reply
against a `TypedDict`, cost per call, a budget check and a trace span. The SDK's own
retries are off, so retries happen in exactly one place. I chose this after seeing how
easily resilience logic drifts when each agent handles failures its own way. With one
path, a guarantee holds for every agent once a test proves it for one: the injected
failure tests show that every node, with every dependency failing, still ends cleanly.

## A bug and how it was resolved

The first benchmark run on 2026-10-20 passed only 4 of 10 requirements. Six items ended
with `qa_failed` before a single test ran, and the environment wasn't the cause: the MCP
session and the sandboxed pytest both worked on a copy of a failed workspace. The cause
was QA's very first reply, the one that writes the test files, being rejected for three
different reasons:

- In four items, a test file listed an acceptance criterion that wasn't copied word for
  word from the specification. The check was correct, but one mismatched string failed
  the whole iteration.
- In one item, a test file path was outside `tests/`.
- In one item, the JSON reply was cut off at the output-token limit. QA asked for
  thinking at `high` effort plus whole test files in a single reply, and never checked
  `stop_reason == "max_tokens"`.

The common flaw was that QA treated any bad reply as final. The fix had three parts:

1. Check every QA reply in full before anything is written, which also stopped
   half-written suites when a later file in a reply was bad.
2. Give a rejected, invalid or cut-off reply exactly one corrective attempt, sending the
   original prompt again with the reason appended.
3. Keep refusals and failed calls non-retryable.

Five new tests and three updated ones cover it. The re-run passed **9 of 10**, and I kept
both results files ([before](../benchmarks/results/20261020T043138Z-before-qa-fix.json),
[after](../benchmarks/results/20261020T053121Z-baseline.json)) so the comparison stays
honest.

A smaller bug turned up while I was building the offline demo. QA's final report counted
every blocking finding an iteration had *ever* seen, so a passing review read "7 passed,
0 failed, 1 blocking". The report now uses the same open-or-disputed rule as the verdict,
and a regression test pins it.

## What I would do differently

- **Build the replay harness first.** The offline demo, with scripted model replies, a
  simulated sandbox and the real graph, broker and MCP server, came last. It found a real
  bug in minutes. Built on day one, it would have been the fastest feedback loop for
  every change.
- **Measure cost per interaction from the start.** Per-agent cost told me *who* was
  expensive but not *which call*. Tagging every model call with its operation and ranking
  interactions (`python -m cost.audit`) is what makes an optimization measurable instead
  of a guess. See [PERFORMANCE.md](PERFORMANCE.md).
- **Benchmark before changing defaults.** I moved the Coder and QA to a cheaper model
  before re-running the benchmark on it. The pass rate for that configuration should have
  been measured first. [BENCHMARK.md](BENCHMARK.md) now reports every configuration
  separately.
- **Plan smaller for small requirements.** The PM can split a one-file tool into several
  tasks, each with its own Coder session. A size-aware plan would save calls on the
  smallest jobs.
- **Make the sandbox swappable earlier.** The Coder used to hard-wire Docker and Chroma.
  Injecting the runner and memory store, as QA already did for its test runner, made the
  offline demo possible and the tests simpler.
