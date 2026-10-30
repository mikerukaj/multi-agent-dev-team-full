"""Per-interaction cost: what each agent operation cost, ranked, and compared between runs.

An *interaction* is one ``(agent, stage, operation)`` triple, for example
``("qa", "qa_review", "QATestFilesReply")``: QA writing its tests. The rows are built
from the ``model_call`` events in each run's ``events.jsonl``, and each run's total is
cross-checked against its cost report, so lost events show up instead of hiding.

Usage:
    python -m cost.audit RUN_DIR [RUN_DIR ...] [--top N] [--json]
    python -m cost.audit --results RESULTS.json [--top N] [--json]
    python -m cost.audit --compare BEFORE.json AFTER.json [--json]
"""

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from cost.report import DEFAULT_DIRECTORY
from observability.events import read_events

TOKEN_FIELDS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_creation_input_tokens": "cache_write_tokens",
    "cache_read_input_tokens": "cache_read_tokens",
}
BILLED = ("input_tokens", "output_tokens", "cache_write_tokens")
MISMATCH_TOLERANCE_USD = 0.0001


def read_model_calls(run_dir: Path) -> list[dict]:
    """The ``model_call`` events of one run; an event without an operation is ``unknown``."""
    calls = []
    for event in read_events(Path(run_dir) / "events.jsonl"):
        if event.get("event") != "model_call":
            continue
        details = {"operation": "unknown", **event.get("details", {})}
        calls.append({**event, "details": details})
    return calls


def interaction_rows(events: Iterable[dict]) -> list[dict]:
    """One row per ``(agent, stage, operation)``, summing calls, tokens and cost."""
    rows: dict[tuple, dict] = {}
    for event in events:
        details = event["details"]
        key = (event["agent"], event["stage"], details["operation"])
        row = rows.setdefault(key, _empty_row(*key))
        row["models"].add(details.get("model", "unknown"))
        row["calls"] += event.get("outcome") == "ok"
        for source, target in TOKEN_FIELDS.items():
            row[target] += (details.get("tokens") or {}).get(source, 0)
        if details.get("cost_usd") is None:
            row["unpriced_calls"] += event.get("outcome") == "ok"
        else:
            row["cost_usd"] = round(row["cost_usd"] + details["cost_usd"], 8)
    for row in rows.values():
        row["billed_tokens"] = sum(row[field] for field in BILLED)
        row["model"] = "+".join(sorted(row.pop("models")))
    return list(rows.values())


def _empty_row(agent: str, stage: str, operation: str) -> dict:
    return {"agent": agent, "stage": stage, "operation": operation, "models": set(),
            "calls": 0, "unpriced_calls": 0, "cost_usd": 0.0,
            **{field: 0 for field in TOKEN_FIELDS.values()}}


def rank(rows: list[dict]) -> list[dict]:
    """Rows by cost, then billed tokens, each with its ``share`` of the total cost."""
    total = sum(row["cost_usd"] for row in rows)
    ranked = sorted(rows, key=lambda row: (row["cost_usd"], row["billed_tokens"]), reverse=True)
    return [{**row, "share": round(row["cost_usd"] / total, 4) if total else 0.0}
            for row in ranked]


def run_dirs_from_results(path: Path) -> list[tuple[Path, dict]]:
    """``(run folder, record)`` for every record of a benchmark results file.

    A run's record folder is ``<workspace root>/.runs/<run_id>``, next to its workspace.
    Records without a workspace (a run that crashed before starting) are skipped.
    """
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    pairs = []
    for record in result.get("records", []):
        if record.get("workspace") and record.get("run_id"):
            run_dir = Path(record["workspace"]).parent / ".runs" / record["run_id"]
            pairs.append((run_dir, record))
    return pairs


def check_cost_report(run_dir: Path, record: dict, events: list[dict]) -> str | None:
    """A warning when the run's event cost and its cost report disagree, else ``None``."""
    run_id = record.get("run_id") or Path(run_dir).name
    path = Path(record.get("cost_report") or DEFAULT_DIRECTORY / f"{run_id}.json")
    try:
        reported = json.loads(path.read_text(encoding="utf-8"))["total"]["cost_usd"]
    except (OSError, ValueError, KeyError) as error:
        return f"{run_id}: cost report {path} unreadable ({type(error).__name__})"
    summed = sum(event["details"].get("cost_usd") or 0.0 for event in events)
    if reported is None or abs(summed - reported) > MISMATCH_TOLERANCE_USD:
        return f"{run_id}: events sum to ${summed:.4f}, cost report says ${reported}"
    return None


def collect(pairs: list[tuple[Path, dict]]) -> tuple[list[dict], list[str], list[str]]:
    """The model-call events of every run, the cost-report warnings, and missing runs."""
    events, warnings, missing = [], [], []
    for run_dir, record in pairs:
        calls = read_model_calls(run_dir)
        if not calls:
            missing.append(str(run_dir))
            continue
        events.extend(calls)
        warning = check_cost_report(run_dir, record, calls)
        if warning:
            warnings.append(warning)
    return events, warnings, missing


def compare(before: list[dict], after: list[dict]) -> list[dict]:
    """Per-interaction deltas between two sets of rows, ranked by the ``before`` cost."""
    after_by_key = {_key(row): row for row in after}
    keys = [_key(row) for row in rank(before)]
    keys += [_key(row) for row in rank(after) if _key(row) not in keys]
    before_by_key = {_key(row): row for row in before}
    return [_delta(key, before_by_key.get(key), after_by_key.get(key)) for key in keys]


def _key(row: dict) -> tuple:
    return row["agent"], row["stage"], row["operation"]


def _delta(key: tuple, before: dict | None, after: dict | None) -> dict:
    empty = {"billed_tokens": 0, "cost_usd": 0.0, "calls": 0}
    old, new = before or empty, after or empty
    return {
        "agent": key[0], "stage": key[1], "operation": key[2],
        "before": before, "after": after,
        "delta_tokens": new["billed_tokens"] - old["billed_tokens"],
        "delta_tokens_pct": _pct(old["billed_tokens"], new["billed_tokens"]),
        "delta_cost": round(new["cost_usd"] - old["cost_usd"], 8),
        "delta_cost_pct": _pct(old["cost_usd"], new["cost_usd"]),
        "per_call_delta_tokens_pct": _pct(_per_call(old), _per_call(new)),
    }


def _per_call(row: dict) -> float | None:
    return row["billed_tokens"] / row["calls"] if row["calls"] else None


def _pct(old: float | None, new: float | None) -> float | None:
    if not old or new is None:
        return None
    return round((new - old) / old * 100, 1)


def run_summary(results_path: Path) -> list[dict]:
    """Per task: status, end reason, tokens and cost, from a benchmark results file."""
    records = json.loads(Path(results_path).read_text(encoding="utf-8")).get("records", [])
    return [{"id": record["id"], "status": record["status"],
             "end_reason": record.get("end_reason"), "succeeded": record.get("succeeded"),
             "tokens": record.get("input_tokens", 0) + record.get("output_tokens", 0),
             "cost_usd": record.get("cost_usd")} for record in records]


def format_table(rows: list[dict], warnings: list[str], top: int) -> str:
    """The ranked interactions as a plain-text table, then any cost-report warnings."""
    lines = [f"{'agent':<6} {'stage':<12} {'operation':<22} {'calls':>5} "
             f"{'billed tok':>11} {'cache read':>11} {'cost $':>9} {'share':>6}"]
    for row in rows[:top]:
        lines.append(f"{row['agent']:<6} {row['stage']:<12} {row['operation']:<22} "
                     f"{row['calls']:>5} {row['billed_tokens']:>11,} "
                     f"{row['cache_read_tokens']:>11,} {row['cost_usd']:>9.4f} "
                     f"{row['share']:>6.1%}")
    lines += [f"warning: {warning}" for warning in warnings]
    return "\n".join(lines)


def format_comparison(rows: list[dict], top: int) -> str:
    """The before/after deltas as a plain-text table."""
    lines = [f"{'agent':<6} {'stage':<12} {'operation':<22} {'Δ tokens':>10} {'Δ tok %':>8} "
             f"{'Δ/call %':>9} {'Δ cost $':>9} {'Δ cost %':>9}"]
    for row in rows[:top]:
        lines.append(f"{row['agent']:<6} {row['stage']:<12} {row['operation']:<22} "
                     f"{row['delta_tokens']:>10,} {_show(row['delta_tokens_pct']):>8} "
                     f"{_show(row['per_call_delta_tokens_pct']):>9} "
                     f"{row['delta_cost']:>9.4f} {_show(row['delta_cost_pct']):>9}")
    return "\n".join(lines)


def _show(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f}"


def main(argv: list[str] | None = None) -> int:
    """Print the ranked interactions or a comparison; 2 when no run has readable events."""
    args = _parse_args(argv)
    if args.compare:
        return _compare_main(args)
    if args.results:
        pairs = run_dirs_from_results(args.results)
    else:
        pairs = [(Path(run_dir), {}) for run_dir in args.run_dirs]
    if not pairs:
        print("error: give RUN_DIR folders, --results or --compare", file=sys.stderr)
        return 2
    events, warnings, missing = collect(pairs)
    for run_dir in missing:
        print(f"warning: no model calls in {run_dir}/events.jsonl", file=sys.stderr)
    if not events:
        return 2
    rows = rank(interaction_rows(events))
    if args.json:
        print(json.dumps({"interactions": rows, "cost_report_mismatch": warnings}, indent=2))
    else:
        print(format_table(rows, warnings, args.top))
    return 0


def _compare_main(args: argparse.Namespace) -> int:
    before_path, after_path = args.compare
    sides = []
    for path in (before_path, after_path):
        events, warnings, missing = collect(run_dirs_from_results(path))
        for run_dir in missing:
            print(f"warning: no model calls in {run_dir}/events.jsonl", file=sys.stderr)
        if not events:
            print(f"error: no run in {path} has readable events", file=sys.stderr)
            return 2
        sides.append((interaction_rows(events), warnings))
    rows = compare(sides[0][0], sides[1][0])
    runs = {"before": run_summary(before_path), "after": run_summary(after_path)}
    warnings = sides[0][1] + sides[1][1]
    if args.json:
        print(json.dumps({"interactions": rows, "runs": runs,
                          "cost_report_mismatch": warnings}, indent=2))
    else:
        print(format_comparison(rows, args.top))
        print("\n".join(f"warning: {warning}" for warning in warnings))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m cost.audit",
        description="Rank agent interactions by cost, or compare two sets of runs.",
    )
    parser.add_argument("run_dirs", nargs="*", help="run record folders (.runs/<run_id>)")
    parser.add_argument("--results", type=Path, help="a benchmark results file")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BEFORE", "AFTER"),
                        help="two benchmark results files to compare")
    parser.add_argument("--top", type=int, default=10, help="rows to show (default 10)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
