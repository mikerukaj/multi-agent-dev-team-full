# Performance audit

Where a run's tokens and money go, which agent interaction costs the most, and one
measured optimization of it.

## Method

1. **Attribute every call.** Every `model_call` event records its agent, stage and
   *operation*: the reply type it asked for (for example `PMSpecReply` or
   `QATestFilesReply`), or `tool_turn` for a Coder tool-loop step.
2. **Rank interactions.** `python -m cost.audit --results <before>.json` groups the calls
   of the three [end-to-end tasks](E2E_RESULTS.md) by `(agent, stage, operation)` and
   ranks them by cost, with tokens alongside. It cross-checks every run's event total
   against its cost report.
3. **Optimize the top interaction** with the first lever that applies, in this order:
   a tighter prompt or output, better prompt caching, lower effort for that step, or a
   smaller model for that step.
4. **Re-run the same three tasks** and compare with
   `python -m cost.audit --compare <before>.json <after>.json`.

The deciding figure is the targeted interaction's **billed tokens per call**, summed over
the three tasks. It must fall by at least 20%, and no task's pass/fail status may get
worse. It's measured per call because the number of calls depends on how many fix rounds
a run needs. Per-run tokens and cost are reported alongside. If the first lever falls
short, it is reverted and the next one is tried, at most two in all.

**Prediction, to be confirmed by the data:** the PM's spec call (`PMSpecReply`) is the
most expensive interaction, because it runs on Sonnet at `high` effort and a Sonnet
output token costs 20 times a Haiku one. The Coder's tool loop is likely the largest by
tokens.

## Before

**Not yet measured.** The end-to-end runs are waiting on a valid API key (see
[E2E_RESULTS.md](E2E_RESULTS.md)).

## Highest-cost interaction

Not yet measured.

## Optimization

Not yet made: it is chosen from the measurement above.

## After

Not yet measured.

## Result

Not yet measured.
